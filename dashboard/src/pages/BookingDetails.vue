<template>
	<BookingHeader :booking-id="bookingId" />

	<div class="flex items-center justify-center p-12" v-if="bookingDetails.loading">
		<Spinner class="w-8 h-8 text-blue-600" />
	</div>

	<!-- Error state: shown when the API fails (e.g. permission error on staging) -->
	<div
		v-else-if="bookingDetails.error && !bookingDetails.data"
		class="flex flex-col items-center justify-center py-16 text-center"
	>
		<div class="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mb-4">
			<LucideXCircle class="w-8 h-8 text-red-400" />
		</div>
		<h3 class="text-base font-semibold text-ink-gray-8 mb-1">
			{{ isPaymentSuccess ? __("Payment received — loading your booking...") : __("Could not load booking") }}
		</h3>
		<p class="text-sm text-ink-gray-5 mb-6 max-w-sm">
			{{
				isPaymentSuccess
					? __("Your payment was successful. We're retrieving your booking details — please wait a moment.")
					: __("We were unable to load this booking. Please try again or contact support.")
			}}
		</p>
		<div class="flex gap-3">
			<Button @click="bookingDetails.reload()" variant="solid">
				{{ __("Retry") }}
			</Button>
			<Button @click="$router.push('/account/bookings')" variant="ghost">
				{{ __("My Bookings") }}
			</Button>
		</div>
	</div>

	<div v-else-if="bookingDetails.data">
		<!-- Success Message for Paid Bookings -->
		<SuccessMessage
			v-if="isPaymentSuccess"
			class="mb-6"
			title="Payment Successful!"
			description="Your booking is confirmed. Your tickets are ready below."
		/>

		<!-- Approval Pending Status (Offline) -->
		<div
			v-if="!booking.event?.free_webinar && isOfflinePaymentPending"
			class="mb-6"
		>
			<div class="p-4 rounded-lg border bg-yellow-50 border-yellow-200">
				<div class="flex items-center gap-3">
					<div
						class="w-8 h-8 rounded-full bg-yellow-100 flex items-center justify-center"
					>
						<LucideClock class="w-4 h-4 text-yellow-600" />
					</div>
					<div class="flex-1">
						<h3 class="font-semibold text-yellow-800">
							{{ __("Payment Confirmation Pending") }}
						</h3>
						<p class="text-sm text-yellow-700">
							{{
								__(
									"Your booking is confirmed subject to verifying the offline payment details. You will be notified once payment is verified."
								)
							}}
						</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Rejected Status -->
		<div v-if="isBookingRejected" class="mb-6">
			<div class="p-4 rounded-lg border bg-red-50 border-red-200">
				<div class="flex items-center gap-3">
					<div class="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center">
						<LucideXCircle class="w-4 h-4 text-red-600" />
					</div>
					<div class="flex-1">
						<h3 class="font-semibold text-red-800">
							{{ __("Booking Rejected") }}
						</h3>
						<p class="text-sm text-red-700">
							{{
								__(
									"Your booking has been rejected. Please contact the event organizer for more information."
								)
							}}
						</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Event Information and Payment Summary in two columns -->
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
			<!-- Event Information -->
			<BookingEventInfo
				v-if="booking.event"
				:event="booking.event"
				:venue="booking.venue"
			/>

			<!-- Booking Financial Summary (from doc) -->
			<BookingFinancialSummary
				v-if="!booking.event?.free_webinar && booking.doc"
				:booking="booking.doc"
			/>

			<!-- Booking Financial Summary (from booking_summary) -->
			<BookingFinancialSummary
				v-if="
					!booking.event?.free_webinar &&
					booking.booking_summary &&
					!isOfflinePaymentPending
				"
				:summary="booking.booking_summary"
			/>
		</div>

		<!-- Cancellation Request Section -->
		<!-- Only show if there's a pending cancellation request (not yet submitted/accepted) -->
		<CancellationRequestNotice
			v-if="!booking.event?.free_webinar && hasPendingCancellationRequest"
			:cancellation-request="booking.cancellation_request"
		/>

		<!-- Tickets Section -->
		<TicketsSection
			v-if="isPaid && !booking.event?.free_webinar"
			:tickets="booking.tickets"
			:can-request-cancellation="canRequestCancellation"
			:can-transfer-tickets="canTransferTickets"
			:can-change-add-ons="canChangeAddOns"
			:cancellation-request="booking.cancellation_request"
			:cancellation-requested-tickets="booking.cancellation_requested_tickets"
			:cancelled-tickets="booking.cancelled_tickets"
			@request-cancellation="showCancellationDialog = true"
			@transfer-success="onTicketTransferSuccess"
		/>

		<CancellationRequestDialog
			v-if="isPaid && !isOfflinePaymentPending"
			v-model="showCancellationDialog"
			:tickets="booking.tickets"
			:booking-id="bookingId"
			:cancellation-requested-tickets="booking.cancellation_requested_tickets"
			:cancelled-tickets="booking.cancelled_tickets"
			@success="onCancellationRequestSuccess"
		/>
	</div>
</template>

<script setup>
import { useBookingFormStorage } from "@/composables/useBookingFormStorage";
import { usePaymentSuccess } from "@/composables/usePaymentSuccess";
import { Spinner, createResource } from "frappe-ui";
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import LucideClock from "~icons/lucide/clock";
import LucideXCircle from "~icons/lucide/x-circle";
import BookingEventInfo from "../components/BookingEventInfo.vue";
import BookingFinancialSummary from "../components/BookingFinancialSummary.vue";
import BookingHeader from "../components/BookingHeader.vue";
import CancellationRequestDialog from "../components/CancellationRequestDialog.vue";
import CancellationRequestNotice from "../components/CancellationRequestNotice.vue";
import SuccessMessage from "../components/SuccessMessage.vue";
import TicketsSection from "../components/TicketsSection.vue";

const route = useRoute();

const props = defineProps({
	bookingId: {
		type: String,
		required: true,
	},
});

/**
 * Normalize the API response shape.
 *
 * Frappe Cloud (staging) wraps whitelisted method responses in a `message`
 * key: `{ message: { event, doc, tickets, ... } }`.
 * Local dev returns the dict directly: `{ event, doc, tickets, ... }`.
 *
 * This computed property transparently handles both shapes so the rest of
 * the component never needs to care which environment it's running in.
 */
const booking = computed(() => {
	return bookingDetails.data?.message || bookingDetails.data || {};
});

// Derived status from backend data
const isPaid = computed(() => {
	return booking.value?.doc?.payment_status === "Paid";
});

// Check if this is an offline payment that is waiting for manual verification
const isOfflinePaymentPending = computed(() => {
	// Only show "Pending Verification" if not already paid and explicitly in Approval Pending state
	return !isPaid.value && booking.value?.doc?.status === "Approval Pending";
});

const isBookingRejected = computed(() => {
	return booking.value?.doc?.status === "Rejected";
});

// Detect success from either the URL redirect OR the actual verified payment status
const isPaymentSuccess = computed(() => {
	return route.query.success === "true" || isPaid.value;
});

const isConfirmationPending = route.query.offline === "true";

// Use payment success composable for confetti and success messages
const { showSuccessMessage } = usePaymentSuccess({
	enableConfetti: computed(() => isPaid.value && !isConfirmationPending),
});

const showCancellationDialog = ref(false);

const bookingDetails = createResource({
	url: "buzz.api.get_booking_details",
	params: { booking_id: props.bookingId },
	auto: true,
	onSuccess: (data) => {
		// Unwrap message key if present (Frappe Cloud wraps responses)
		const normalized = data?.message || data || {};
		// Clear stored booking form data if this was a successful payment
		if (isPaymentSuccess.value && normalized?.event?.route) {
			const { clearStoredData } = useBookingFormStorage(normalized.event.route);
			clearStoredData();
		}
	},
});

const canTransferTickets = computed(() => {
	return booking.value?.can_transfer_ticket?.can_transfer || false;
});

const canChangeAddOns = computed(() => {
	return booking.value?.can_change_add_ons?.can_change_add_ons || false;
});

const canRequestCancellation = computed(() => {
	return booking.value?.can_request_cancellation?.can_request_cancellation || false;
});

// Only show cancellation notice if there's a pending request (not yet submitted)
const hasPendingCancellationRequest = computed(() => {
	const cancellationRequest = booking.value?.cancellation_request;
	const cancellationRequestedTickets = booking.value?.cancellation_requested_tickets || [];

	// Show notice only if there's a cancellation request AND there are tickets with pending cancellation
	return cancellationRequest && cancellationRequestedTickets.length > 0;
});

const onTicketTransferSuccess = () => {
	bookingDetails.reload();
};

const onCancellationRequestSuccess = (data) => {
	bookingDetails.reload();
};

onMounted(() => {
	// If redirected from successful payment, force a fresh load to bypass any cache
	if (isPaymentSuccess.value) {
		bookingDetails.reload();
	}
});
</script>
