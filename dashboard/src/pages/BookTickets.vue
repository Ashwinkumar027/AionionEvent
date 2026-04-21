<template>
	<div>
		<div class="w-8">
			<Spinner v-if="eventBookingResource.loading" />
		</div>
		<div
			v-if="eventNotFound && !eventBookingResource.loading"
			class="flex flex-col items-center justify-center py-16 px-4"
		>
			<div class="text-center max-w-md">
				<h2 class="text-xl font-semibold text-ink-gray-8 mb-2">
					{{ __("Event Not Found") }}
				</h2>
				<p class="text-ink-gray-6 mb-6">
					{{
						__(
							"The event you are looking for does not exist or may have been removed."
						)
					}}
				</p>
				<Button variant="solid" size="lg" @click="$router.push('/')">{{
					__("Go to Home")
				}}</Button>
			</div>
		</div>
		<div
			v-else-if="registrationsClosed && !eventBookingResource.loading"
			class="flex flex-col items-center justify-center py-16 px-4"
		>
			<div class="text-center max-w-md">
				<img
					v-if="eventBookingData.eventDetails?.banner_image"
					:src="eventBookingData.eventDetails.banner_image"
					:alt="eventBookingData.eventDetails.title"
					class="w-full rounded-lg mb-6 object-cover max-h-48"
				/>
				<h2 class="text-xl font-semibold text-ink-gray-8 mb-2">
					{{ __("Registrations Closed") }}
				</h2>
				<p class="text-ink-gray-6 mb-6">
					{{ __("Registrations for this event are closed.") }}
				</p>
				<Button variant="solid" size="lg" @click="goToHome">{{
					__("Browse Other Events")
				}}</Button>
			</div>
		</div>
		<div
			v-else-if="loadError && !eventBookingResource.loading"
			class="flex flex-col items-center justify-center py-16 px-4"
		>
			<div class="text-center max-w-md">
				<h2 class="text-xl font-semibold text-ink-gray-8 mb-2">
					{{ __("Booking Unavailable") }}
				</h2>
				<p class="text-ink-gray-6 mb-6">
					{{ loadError }}
				</p>
				<Button variant="solid" size="lg" @click="eventBookingResource.fetch()">
					{{ __("Try Again") }}
				</Button>
			</div>
		</div>
		<div v-else>
			<BookingForm
				v-if="eventBookingData.available_add_ons && eventBookingData.available_ticket_types"
				:event-details="eventBookingData.event_details"
				:available-ticket-types="eventBookingData.available_ticket_types"
				:available-add-ons="eventBookingData.available_add_ons"
				:tax-settings="eventBookingData.tax_settings"
				:custom-fields="eventBookingData.custom_fields"
				:payment-gateways="eventBookingData.payment_gateways"
				:offline-payment-enabled="eventBookingData.offline_payment_enabled"
				:offline-methods="eventBookingData.offline_methods"
				:is-guest-mode="isGuest"
			/>
		</div>
	</div>
</template>

<script setup>
import { session } from "@/data/session";
import { Spinner, createResource } from "frappe-ui";
import { computed, reactive, ref } from "vue";
import BookingForm from "../components/BookingForm.vue";

const eventBookingData = reactive({
	available_add_ons: null,
	available_ticket_types: null,
	tax_settings: null,
	event_details: null,
	custom_fields: null,
	payment_gateways: [],
	offline_methods: [],
});

const eventNotFound = ref(false);
const registrationsClosed = ref(false);
const loadError = ref(null);

const props = defineProps({
	eventRoute: {
		type: String,
		required: true,
	},
});

const isGuest = computed(() => !session.isLoggedIn);

const goToHome = () => {
	window.location.href = "/";
};

const eventBookingResource = createResource({
	url: "buzz.api.get_event_booking_data",
	params: {
		event_route: props.eventRoute,
	},
	auto: true,
	onSuccess: (data) => {
		eventBookingData.available_add_ons = data.available_add_ons || [];
		eventBookingData.available_ticket_types = data.available_ticket_types || [];
		eventBookingData.tax_settings = data.tax_settings || {
			apply_tax: false,
			tax_inclusive: false,
			tax_label: "Tax",
			tax_percentage: 0,
		};
		eventBookingData.event_details = data.event_details || {};
		eventBookingData.custom_fields = data.custom_fields || [];
		eventBookingData.payment_gateways = data.payment_gateways || [];
		eventBookingData.offline_methods = data.offline_methods || [];
		registrationsClosed.value = data.registrations_closed || false;
	},
	onError: (error) => {
		if (error.message?.includes("DoesNotExistError")) {
			eventNotFound.value = true;
		} else {
			loadError.value = error.message || "Failed to load booking data";
		}
	},
});
</script>
