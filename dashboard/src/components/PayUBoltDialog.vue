<!-- PayUBoltDialog.vue
     Integrates PayU Bolt (inline / modal checkout) so the payment flow
     never leaves the application.

     Props
     ─────
       bookingId       – Event Booking docname
       paymentGateway  – e.g. "PayU"  (forwarded to backend hash API)

     Events
     ──────
       payment-success  – emitted with { bookingId }  after confirmation
       payment-failure  – emitted with { message }
       close            – emitted when the user cancels / dialog closes
-->
<template>
  <div>
    <!-- Full-screen backdrop loader while we fetch Bolt params or wait for SDK -->
    <div
      v-if="state === 'loading'"
      class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <div class="bg-white rounded-2xl shadow-2xl p-10 flex flex-col items-center gap-5 max-w-sm w-full mx-4">
        <div class="relative w-14 h-14">
          <!-- Animated ring -->
          <svg class="animate-spin w-14 h-14 text-blue-600" viewBox="0 0 56 56" fill="none">
            <circle cx="28" cy="28" r="24" stroke="currentColor" stroke-width="4" stroke-linecap="round"
              stroke-dasharray="120" stroke-dashoffset="80" opacity="0.25" />
            <circle cx="28" cy="28" r="24" stroke="currentColor" stroke-width="4" stroke-linecap="round"
              stroke-dasharray="120" stroke-dashoffset="80" />
          </svg>
          <!-- PayU logo inside spinner -->
          <span class="absolute inset-0 flex items-center justify-center text-xs font-black text-blue-700 select-none">
            PAY<span class="text-orange-500">U</span>
          </span>
        </div>
        <div class="text-center">
          <p class="text-ink-gray-8 font-semibold text-base">{{ __("Preparing Secure Payment") }}</p>
          <p class="text-ink-gray-5 text-sm mt-1">{{ __("Please wait while we set up your checkout…") }}</p>
        </div>
      </div>
    </div>

    <!-- Error state (API/SDK failure) -->
    <div
      v-else-if="state === 'error'"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
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

    <!-- Confirming payment after Bolt closes -->
    <div
      v-else-if="state === 'confirming'"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <div class="bg-white rounded-2xl shadow-2xl p-10 flex flex-col items-center gap-5 max-w-sm w-full mx-4">
        <div class="w-14 h-14 rounded-full bg-blue-50 flex items-center justify-center animate-pulse">
          <svg class="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <p class="text-ink-gray-8 font-semibold text-base">{{ __("Confirming Payment…") }}</p>
        <p class="text-ink-gray-5 text-sm">{{ __("Verifying your transaction with our server") }}</p>
      </div>
    </div>

    <!-- Success state -->
    <div
      v-else-if="state === 'success'"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <div class="bg-white rounded-2xl shadow-2xl p-10 flex flex-col items-center gap-4 max-w-sm w-full mx-4 text-center">
        <div class="w-16 h-16 rounded-full bg-green-50 flex items-center justify-center animate-bounce">
          <svg class="w-9 h-9 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 class="text-xl font-bold text-ink-gray-9">{{ __("Payment Successful!") }}</h3>
        <p class="text-sm text-ink-gray-6">{{ __("Your booking is confirmed. Redirecting…") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Button, createResource, toast } from "frappe-ui";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

// ── Props & emits ────────────────────────────────────────────────────────────
const props = defineProps({
  bookingId: { type: String, required: true },
  paymentGateway: { type: String, default: null },
});

const emit = defineEmits(["payment-success", "payment-failure", "close"]);

// ── State machine ────────────────────────────────────────────────────────────
// "loading" → "bolt-open" (Bolt is running) → "confirming" → "success" | "error"
const state = ref("loading"); // loading | bolt-open | confirming | success | error
const errorMessage = ref("");
const router = useRouter();

// ── PayU Bolt SDK URL ────────────────────────────────────────────────────────
const BOLT_SDK_TEST = "https://sboxcheckout-static.citruspay.com/bolt/run/bolt.min.js";
const BOLT_SDK_PROD = "https://checkout-static.citruspay.com/bolt/run/bolt.min.js";

// ── Helpers ──────────────────────────────────────────────────────────────────
/**
 * Dynamically load the PayU Bolt SDK <script> tag.
 * Returns a promise that resolves when the SDK is ready.
 */
function loadBoltSdk(env) {
  return new Promise((resolve, reject) => {
    const sdkUrl = env === "production" ? BOLT_SDK_PROD : BOLT_SDK_TEST;

    // Avoid double-loading
    const existing = document.querySelector(`script[src="${sdkUrl}"]`);
    if (existing) {
      resolve();
      return;
    }

    const script = document.createElement("script");
    script.src = sdkUrl;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load PayU Bolt SDK"));
    document.head.appendChild(script);
  });
}

// ── Frappe API resources ─────────────────────────────────────────────────────
const getPayuData = createResource({
  url: "buzz.api.get_payu_payment_data",
});

const confirmPayment = createResource({
  url: "buzz.api.confirm_payu_payment",
});

// ── Core flow ────────────────────────────────────────────────────────────────
async function initPayment() {
  state.value = "loading";
  errorMessage.value = "";

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

  // Load Bolt SDK
  try {
    await loadBoltSdk(payuParams.environment);
  } catch (err) {
    errorMessage.value = __("Could not load PayU checkout. Check your internet connection.");
    state.value = "error";
    emit("payment-failure", { message: errorMessage.value });
    return;
  }

  if (!window.bolt) {
    errorMessage.value = __("PayU Bolt SDK is not available. Please refresh and try again.");
    state.value = "error";
    return;
  }

  // ── Launch Bolt ────────────────────────────────────────────────────────────
  state.value = "bolt-open";

  window.bolt.launch(
    {
      key: payuParams.key,
      txnid: payuParams.txnid,
      hash: payuParams.hash,
      amount: payuParams.amount,
      firstname: payuParams.firstname,
      email: payuParams.email,
      phone: payuParams.phone,
      productinfo: payuParams.productinfo,
      surl: payuParams.surl,
      furl: payuParams.furl,
    },
    {
      responseHandler: async function (BOLT) {
        const response = BOLT.response || {};
        const txnStatus = (response.txnStatus || "").toUpperCase();

        if (txnStatus === "SUCCESS" || txnStatus === "CAPTURED") {
          state.value = "confirming";

          try {
            const result = await confirmPayment.submit({
              txnid: payuParams.txnid,
              mihpayid: response.mihpayid || "",
              status: "success",
              received_hash: response.hash || "",
            });

            if (result?.success) {
              state.value = "success";
              emit("payment-success", { bookingId: props.bookingId });

              // Redirect to booking details after a short delay
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
          // Payment is pending – let the user know
          toast.warning(
            __(
              "Your payment is pending. We will update your booking once confirmed."
            )
          );
          handleClose();
        } else {
          // Failed / cancelled
          const msg =
            response.field9 || // PayU error description
            __("Payment was not completed. Please try again.");
          errorMessage.value = msg;
          state.value = "error";
          emit("payment-failure", { message: msg });
        }
      },

      catchException: function (BOLT) {
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
  state.value = "loading"; // reset
  emit("close");
}

// Auto-start when the component mounts
onMounted(() => {
  initPayment();
});
</script>
