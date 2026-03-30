<template>
	<div class="space-y-1.5">
		<label class="text-xs text-ink-gray-5 block">
			{{ __(label) }}
			<span v-if="required" class="text-ink-red-4">*</span>
		</label>
		<div class="relative">
			<input
				:id="inputId"
				ref="phoneInputEl"
				type="tel"
				class="iti-phone-input"
				:placeholder="placeholder || __('Enter phone number')"
				autocomplete="tel"
			/>
		</div>
		<p v-if="errorMessage" class="text-xs text-ink-red-4 mt-1">{{ errorMessage }}</p>
	</div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
	modelValue: { type: String, default: "" },
	label: { type: String, default: "Phone" },
	placeholder: { type: String, default: "" },
	required: { type: Boolean, default: false },
	inputId: { type: String, default: () => `phone-input-${Math.random().toString(36).slice(2, 9)}` },
});

const emit = defineEmits(["update:modelValue", "valid", "invalid"]);

const phoneInputEl = ref(null);
const errorMessage = ref("");
let itiInstance = null;
let itiReady = false;

// ── 1. CDN loader helpers

const ITI_CSS =
	"https://cdn.jsdelivr.net/npm/intl-tel-input@23/build/css/intlTelInput.css";
const ITI_JS =
	"https://cdn.jsdelivr.net/npm/intl-tel-input@23/build/js/intlTelInput.min.js";
const ITI_UTILS =
	"https://cdn.jsdelivr.net/npm/intl-tel-input@23/build/js/utils.js";

function loadCSS(href) {
	if (document.querySelector(`link[href="${href}"]`)) return;
	const link = document.createElement("link");
	link.rel = "stylesheet";
	link.href = href;
	document.head.appendChild(link);
}

function loadScript(src) {
	return new Promise((resolve, reject) => {
		if (document.querySelector(`script[src="${src}"]`)) {
			// Already injected – wait until window.intlTelInput is available
			const poll = setInterval(() => {
				if (window.intlTelInput) {
					clearInterval(poll);
					resolve();
				}
			}, 50);
			return;
		}
		const script = document.createElement("script");
		script.src = src;
		script.async = true;
		script.onload = resolve;
		script.onerror = reject;
		document.head.appendChild(script);
	});
}

// ── 2. Init intl-tel-input

async function initIti() {
	loadCSS(ITI_CSS);
	await loadScript(ITI_JS);

	if (!phoneInputEl.value) return;

	itiInstance = window.intlTelInput(phoneInputEl.value, {
		utilsScript: ITI_UTILS,
		initialCountry: "auto",
		geoIpLookup: (success) => {
			fetch("https://ipapi.co/json")
				.then((r) => r.json())
				.then((data) => success(data.country_code))
				.catch(() => success("IN")); // fallback to India
		},
		separateDialCode: true,
		formatOnDisplay: true,
		// No onlyCountries restriction – all countries allowed
	});

	itiReady = true;

	// Set initial value if provided
	if (props.modelValue) {
		itiInstance.setNumber(props.modelValue);
	}

	phoneInputEl.value.addEventListener("input", onInput);
	phoneInputEl.value.addEventListener("countrychange", onInput);
}

function onInput() {
	errorMessage.value = "";
	const num = itiInstance ? itiInstance.getNumber() : "";
	emit("update:modelValue", num);
}

// ── 3. Public validate() method ──────────────────────────────────────────────

function validate() {
	if (!itiReady || !itiInstance) {
		if (props.required) {
			errorMessage.value = __("Phone number is required");
			return false;
		}
		return true;
	}

	const raw = phoneInputEl.value?.value?.trim() || "";

	if (!raw) {
		if (props.required) {
			errorMessage.value = __("Phone number is required");
			emit("invalid");
			return false;
		}
		return true;
	}

	if (!itiInstance.isValidNumber()) {
		const errorCode = itiInstance.getValidationError();
		const messages = {
			1: __("Invalid country dial code"),
			2: __("Phone number is too short"),
			3: __("Phone number is too long"),
			4: __("Phone number is not a valid number"),
		};
		errorMessage.value = messages[errorCode] || __("Please enter a valid phone number");
		emit("invalid");
		return false;
	}

	errorMessage.value = "";
	emit("valid");
	return true;
}

function clearError() {
	errorMessage.value = "";
}

// ── 4. Lifecycle

onMounted(() => {
	initIti();
});

onBeforeUnmount(() => {
	if (itiInstance) {
		itiInstance.destroy();
		itiInstance = null;
		itiReady = false;
	}
});

// Keep in sync when parent changes modelValue externally
watch(
	() => props.modelValue,
	(val) => {
		if (itiReady && itiInstance) {
			const current = itiInstance.getNumber();
			if (val !== current) {
				itiInstance.setNumber(val || "");
			}
		}
	}
);

// Expose validate() so parent can call $refs.phoneRef.validate()
defineExpose({ validate, clearError });
</script>

<style>
/* Ensure the input fills the full width and matches Frappe UI styling */
.iti {
	width: 100%;
	display: block;
}

.iti-phone-input {
	width: 100%;
	height: 2rem;
	font-size: 0.875rem;
	line-height: 1.25rem;
	color: var(--ink-gray-9, #1a1a1a);
	background-color: var(--surface-white, #ffffff);
	border: 1px solid var(--outline-gray-3, #d1d5db);
	border-radius: 0.375rem;
	padding: 0 0.625rem;
	outline: none;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.iti-phone-input:focus {
	border-color: var(--outline-blue-3, #3b82f6);
	box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

/* Ensure the flag dropdown doesn't clip the input */
.iti--separate-dial-code .iti__selected-dial-code {
	font-size: 0.8rem;
}
</style>
