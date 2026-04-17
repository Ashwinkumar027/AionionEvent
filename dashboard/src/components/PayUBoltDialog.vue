<!-- PayUBoltDialog.vue
     Integrates PayU Bolt (inline / modal checkout) so the payment flow
     never leaves the application.

     Props
     -----
       bookingId       - Event Booking docname
       paymentGateway  - e.g. "PayU"  (forwarded to backend hash API)

     Events
     ------
       payment-success  - emitted with { bookingId }  after confirmation
       payment-failure  - emitted with { message }
       close            - emitted when the user cancels / dialog closes

     KEY FIX (vs original):
       PayU Bolt SDK calls document.write() DURING ITS OWN SCRIPT PARSE when it
       receives a 429 Too Many Requests response. This wipes the entire SPA DOM.

       The fix is to:
         1. Install the document.write / document.writeln interceptor BEFORE the
            bolt.min.js <script> tag is appended to the DOM (before loadBoltSdk).
         2. Keep script.async = false so the SDK executes synchronously, keeping
            its document.write calls in the same interceptable call stack.
         3. Intercept both document.write and document.writeln via
            Object.defineProperty (direct assignment silently fails in some envs).
         4. Add a post-load check: if the interceptor already fired during SDK
            load, bail before calling bolt.launch().
         5. Restore originals in every exit path and in onUnmounted.
-->
<template>
  <div>
    <!-- Full-screen backdrop loader -->
    <div
      v-if="state === 'loading'"
      class="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black/70 backdrop-blur-md"
    >
      <div class="bg-white rounded-2xl shadow-2xl p-10 flex flex-col items-center gap-5 max-w-sm w-full mx-4">
        <div class="relative w-14 h-14">
          <svg class="animate-spin w-14 h-14 text-blue-600" viewBox="0 0 56 56" fill="none">
            <circle cx="28" cy="28" r="24" stroke="currentColor" stroke-width="4" stroke-linecap="round"
              stroke-dasharray="120" stroke-dashoffset="80" opacity="0.25" />
            <circle cx="28" cy="28" r="24" stroke="currentColor" stroke-width="4" stroke-linecap="round"
              stroke-dasharray="120" stroke-dashoffset="80" />
          </svg>
          <span class="absolute inset-0 flex items-center justify-center text-xs font-black text-blue-700 select-none">
            PAY<span class="text-orange-500">U</span>
          </span>
        </div>
        <div class="text-center">
          <p class="text-ink-gray-8 font-semibold text-base">{{ __("Preparing Secure Payment") }}</p>
          <p class="text-ink-gray-5 text-sm mt-1">{{ __("Please wait while we set up your checkout...") }}</p>
        </div>
      </div>
    </div>

    <!-- Error state -->
    <div
      v-else-if="state === 'error'"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-md"
    >
      <div class="bg-white rounded-2xl shadow-2xl p-8 max-w-sm w-full mx-4 text-center">
        <div class="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-ink-gray-9 mb-2">{{ __("Payment Error") }}</h3>
        <p class="text-sm text-ink-gray-6 mb-6">{{ errorMessage }}</p>
        <div class="flex gap-3 justify-center">
          <Button variant="ghost" @click="handleClose">{{ __("Cancel") }}</Button>
          <Button variant="solid" @click="initPayment">{{ __("Try Again") }}</Button>
        </div>
      </div>
    </div>

    <!-- Confirming state -->
    <div
      v-else-if="state === 'confirming'"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-md"
    >
      <div class="bg-white rounded-2xl shadow-2xl p-10 flex flex-col items-center gap-5 max-w-sm w-full mx-4">
        <div class="w-14 h-14 rounded-full bg-blue-50 flex items-center justify-center animate-pulse">
          <svg class="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <p class="text-ink-gray-8 font-semibold text-base">{{ __("Confirming Payment...") }}</p>
        <p class="text-ink-gray-5 text-sm">{{ __("Verifying your transaction with our server") }}</p>
      </div>
    </div>

    <!-- Success state -->
    <div
      v-else-if="state === 'success'"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-md"
    >
      <div class="bg-white rounded-2xl shadow-2xl p-10 flex flex-col items-center gap-4 max-w-sm w-full mx-4 text-center">
        <div class="w-16 h-16 rounded-full bg-green-50 flex items-center justify-center animate-bounce">
          <svg class="w-9 h-9 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 class="text-xl font-bold text-ink-gray-9">{{ __("Payment Successful!") }}</h3>
        <p class="text-sm text-ink-gray-6">{{ __("Your booking is confirmed. Redirecting...") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Button, createResource, toast } from "frappe-ui";
import { onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";

// ============================================================
// Props & emits
// ============================================================
const props = defineProps({
  bookingId: { type: String, required: true },
  paymentGateway: { type: String, default: null },
  isPaid: { type: Boolean, default: true },
});

const emit = defineEmits(["payment-success", "payment-failure", "close"]);

// ============================================================
// State machine:  loading -> bolt-open -> confirming -> success
//                         \-> error  (from any stage)
// ============================================================
const state = ref("loading");
const errorMessage = ref("");
const router = useRouter();

// ============================================================
// PayU Bolt SDK URLs
// ============================================================
const BOLT_SDK_TEST = "https://sboxcheckout-static.citruspay.com/bolt/run/bolt.min.js";
const BOLT_SDK_PROD = "https://checkout-static.citruspay.com/bolt/run/bolt.min.js";

// ============================================================
// Error patterns
//
// Sourced from the exact string PayU writes to the DOM on 429:
//   "Sorry, we are unable to process your payment due to Too many
//    Requests. Please try after 60 seconds. Kindly reach out to
//    care@payu.in"
//
// If you see new error variants in the browser console warning
// "[PayUBoltDialog] Unexpected document.write", add them here.
// ============================================================
const PAYU_ERROR_PATTERNS = [
  "too many requests",
  "unable to process your payment",
  "sorry, we are unable",
  "try after 60 seconds",
  "please try after",
  "kindly reach out",
  "care@payu.in",
  "payu.in",
  "rate limit",
];

// ============================================================
// document.write / document.writeln interceptor
// ============================================================
let _origWrite         = null;
let _origWriteln       = null;
let _interceptorActive = false;

/**
 * installInterceptor()
 *
 * Overrides document.write and document.writeln with handlers that:
 *   - Detect PayU error strings and route them into Vue state ("error")
 *     instead of letting them wipe the DOM.
 *   - Pass unrecognised writes through to the original (with a console
 *     warning so developers can spot new patterns).
 *
 * Uses Object.defineProperty rather than direct assignment because in
 * some environments (strict-mode iframes, certain Chromium builds)
 * document.write is non-writable and direct assignment silently fails.
 */
function installInterceptor() {
  if (_interceptorActive) return; // no double-install on retry

  // Capture originals once - they survive across retries
  if (!_origWrite) {
    _origWrite   = document.write.bind(document);
    _origWriteln = document.writeln.bind(document);
  }

  const makeHandler = (fallback) =>
    function interceptedDocWrite(...args) {
      const content = args.join(" ").toLowerCase();

      if (PAYU_ERROR_PATTERNS.some((pattern) => content.includes(pattern))) {
        // Restore immediately so no second write can come through
        restoreDocumentWrite();
        const msg = __("Payment gateway is busy. Please wait 60 seconds and try again.");
        errorMessage.value = msg;
        state.value = "error";
        emit("payment-failure", { message: msg });
        return; // DOM write suppressed - SPA stays intact
      }

      // Unrecognised write - log it so the pattern list can be extended
      console.warn("[PayUBoltDialog] Unexpected document.write intercepted:", args);
      return fallback(...args);
    };

  try {
    Object.defineProperty(document, "write", {
      configurable: true,
      writable: true,
      value: makeHandler(_origWrite),
    });
    Object.defineProperty(document, "writeln", {
      configurable: true,
      writable: true,
      value: makeHandler(_origWriteln),
    });
    _interceptorActive = true;
  } catch (e) {
    // defineProperty not supported - fall back to direct assignment
    console.warn("[PayUBoltDialog] Object.defineProperty failed, using direct assignment:", e);
    document.write   = makeHandler(_origWrite);
    document.writeln = makeHandler(_origWriteln);
    _interceptorActive = true;
  }
}

/**
 * restoreDocumentWrite()
 *
 * Puts the original document.write and document.writeln back.
 * Safe to call multiple times.
 */
function restoreDocumentWrite() {
  if (!_interceptorActive) return;
  try {
    if (_origWrite) {
      Object.defineProperty(document, "write", {
        configurable: true,
        writable: true,
        value: _origWrite,
      });
    }
    if (_origWriteln) {
      Object.defineProperty(document, "writeln", {
        configurable: true,
        writable: true,
        value: _origWriteln,
      });
    }
  } catch (e) {
    if (_origWrite)   document.write   = _origWrite;
    if (_origWriteln) document.writeln = _origWriteln;
  }
  _interceptorActive = false;
}

// ============================================================
// SDK loader
// ============================================================
/**
 * loadBoltSdk(env)
 *
 * Appends the Bolt SDK <script> tag and resolves when it has executed.
 *
 * CRITICAL: script.async is NOT set (defaults to false).
 *
 * When async is true the browser defers execution to a later task.
 * PayU's parse-time document.write would then run in a fresh call stack
 * after our await has already returned, making it harder to guarantee
 * the interceptor is still the active handler at that moment.
 *
 * Keeping the script synchronous means the browser blocks on it: the
 * SDK executes inline, any document.write it calls during parse-time
 * error handling fires while our interceptor is provably installed.
 */
function loadBoltSdk(env) {
  return new Promise((resolve, reject) => {
    const sdkUrl = env === "production" ? BOLT_SDK_PROD : BOLT_SDK_TEST;

    const existing = document.querySelector(`script[src="${sdkUrl}"]`);
    if (existing) {
      resolve();
      return;
    }

    const script = document.createElement("script");
    script.src = sdkUrl;
    // async intentionally omitted - see note above
    script.onload  = () => resolve();
    script.onerror = () => reject(new Error("Failed to load PayU Bolt SDK"));
    document.head.appendChild(script);
  });
}

// ============================================================
// Frappe API resources
// ============================================================
const getPayuData    = createResource({ url: "buzz.api.get_payu_payment_data" });
const confirmPayment = createResource({ url: "buzz.api.confirm_payu_payment" });

// ============================================================
// Core payment flow
// ============================================================
async function initPayment() {
  // Defensive check: do nothing for free bookings
  if (props.isPaid === false) {
    console.warn("[PayUBoltDialog] initPayment called for a free booking. Ignoring.");
    return;
  }

  state.value = "loading";
  errorMessage.value = "";

  // --- STEP 1: Fetch params from our backend ---
  let payuParams;
  try {
    payuParams = await getPayuData.submit({
      booking_id: props.bookingId,
      payment_gateway: props.paymentGateway || null,
    });
  } catch (err) {
    const msg =
      err?.messages?.[0] ||
      err?.message ||
      __("Failed to initialise payment. Please try again.");
    errorMessage.value = msg;
    state.value = "error";
    emit("payment-failure", { message: msg });
    return;
  }

  // --- STEP 2: Install interceptor BEFORE loading the SDK ---
  //
  // This is the root fix for the black-screen bug.
  //
  // What happens without this fix:
  //   loadBoltSdk() appends <script src="bolt.min.js">.
  //   If PayU returns 429, the SDK calls document.write() DURING ITS OWN
  //   PARSE, before onload fires, before any of our code can run again.
  //   document.write() after the page has loaded implicitly calls
  //   document.open(), which wipes the entire DOM - showing a black screen
  //   with just the raw PayU error text.
  //
  // What happens with this fix:
  //   installInterceptor() runs first. Our handler is now the active
  //   document.write. When the SDK's parse-time write fires, our handler
  //   intercepts it, suppresses the DOM write, and sets state to "error"
  //   so Vue renders the error modal instead.
  installInterceptor();

  // --- STEP 3: Load the SDK ---
  try {
    await loadBoltSdk(payuParams.environment);
  } catch (err) {
    restoreDocumentWrite();
    errorMessage.value = __("Could not load PayU checkout. Check your internet connection.");
    state.value = "error";
    emit("payment-failure", { message: errorMessage.value });
    return;
  }

  // --- STEP 3b: Check if interceptor already fired during SDK parse ---
  // If the 429 happened at parse time, the interceptor set state to "error".
  // Do NOT proceed to bolt.launch() in that case.
  if (state.value === "error") return;

  if (!window.bolt) {
    restoreDocumentWrite();
    errorMessage.value = __("PayU Bolt SDK is not available. Please refresh and try again.");
    state.value = "error";
    return;
  }

  // --- STEP 4: Small throttle delay before launch ---
  // Lowers 429 probability when the user retries quickly.
  // Using randomized jitter as requested for production stability.
  await new Promise((r) => setTimeout(r, 2000 + Math.random() * 1000));

  // Bail if state changed during the delay (user cancelled, etc.)
  if (state.value !== "loading") return;

  state.value = "bolt-open";

  // --- STEP 5: Launch the Bolt checkout modal ---
  window.bolt.launch(
    {
      key:         payuParams.key,
      txnid:       payuParams.txnid,
      hash:        payuParams.hash,
      amount:      payuParams.amount,
      firstname:   payuParams.firstname,
      email:       payuParams.email,
      phone:       payuParams.phone,
      productinfo: payuParams.productinfo,
      surl:        payuParams.surl,
      furl:        payuParams.furl,
    },
    {
      responseHandler: async function (BOLT) {
        restoreDocumentWrite();

        const response  = BOLT.response || {};
        const txnStatus = (response.txnStatus || "").toUpperCase();

        if (txnStatus === "SUCCESS" || txnStatus === "CAPTURED") {
          state.value = "confirming";

          try {
            const result = await confirmPayment.submit({
              txnid:         payuParams.txnid,
              mihpayid:      response.mihpayid || "",
              status:        "success",
              payu_response: response,
            });

            if (result?.success) {
              state.value = "success";
              emit("payment-success", { bookingId: props.bookingId });
              setTimeout(() => {
                router.replace(`/bookings/${props.bookingId}?success=true`);
              }, 1800);
            } else {
              const msg = __("Payment could not be confirmed. Please contact support.");
              errorMessage.value = msg;
              state.value = "error";
              emit("payment-failure", { message: msg });
            }
          } catch (err) {
            const msg =
              err?.messages?.[0] ||
              err?.message ||
              __("Payment confirmation failed. Please contact support.");
            errorMessage.value = msg;
            state.value = "error";
            emit("payment-failure", { message: msg });
          }

        } else if (txnStatus === "PENDING" || txnStatus === "PENDING_COMMUNICATION") {
          toast.warning(
            __("Your payment is pending. We will update your booking once confirmed.")
          );
          handleClose();

        } else {
          const msg =
            response.field9 ||
            __("Payment was not completed. Please try again.");
          errorMessage.value = msg;
          state.value = "error";
          emit("payment-failure", { message: msg });
        }
      },

      catchException: function (BOLT) {
        restoreDocumentWrite();
        const msg =
          BOLT?.message ||
          __("An error occurred during payment. Please try again.");
        errorMessage.value = msg;
        state.value = "error";
        emit("payment-failure", { message: msg });
      },
    }
  );
}

function handleClose() {
  restoreDocumentWrite();
  state.value = "loading";
  emit("close");
}

// ============================================================
// Lifecycle
// ============================================================
onMounted(() => {
  if (!props.isPaid) {
    console.warn("[PayUBoltDialog] Skipping PayU for free booking");
    return;
  }

  if (!props.bookingId) {
    console.warn("[PayUBoltDialog] Missing bookingId, skipping PayU");
    return;
  }

  initPayment();
});

onUnmounted(() => {
  // Always clean up - guards against the component being destroyed
  // mid-flow (e.g. parent navigates away while Bolt modal is open).
  restoreDocumentWrite();
});
</script>