<template>
    <Dialog
        v-model="isOpen"
        :options="{
            title: __('Select Payment Method'),
            size: 'md',
        }"
    >
        <template #body-content>
            <div class="space-y-3">
                <div
                    v-for="gateway in paymentGateways"
                    :key="gateway"
                    class="border border-outline-gray-2 rounded-lg p-4 cursor-pointer transition-all hover:border-outline-gray-3 hover:bg-surface-gray-1"
                    :class="{
                        'border-outline-gray-4 bg-surface-gray-2': selectedGateway === gateway,
                    }"
                    @click="selectedGateway = gateway"
                >
                    <div class="flex items-center space-x-3">
                        <input
                            type="radio"
                            :checked="selectedGateway === gateway"
                            @change="selectedGateway = gateway"
                            class="text-ink-gray-6"
                        />
                        <div>
                            <h3 class="font-semibold text-ink-gray-9">{{ gateway }}</h3>
                        </div>
                    </div>
                </div>
            </div>
        </template>
        <template #actions>
            <div class="flex justify-end space-x-3">
                <Button variant="ghost" @click="closeDialog">{{ __("Cancel") }}</Button>
                <Button variant="solid" :disabled="!selectedGateway" @click="proceedToPayment">
                    {{ __("Proceed to Pay") }}
                </Button>
            </div>
        </template>
    </Dialog>
</template>

<script setup>
import { Button, Dialog } from "frappe-ui";
import { computed, ref, watch } from "vue";

const props = defineProps({
    open: {
        type: Boolean,
        default: false,
    },
    paymentGateways: {
        type: Array,
        required: true,
    },
});

const emit = defineEmits(["update:open", "gateway-selected"]);

const isOpen = computed({
    get: () => props.open,
    set: (val) => emit("update:open", val),
});

const selectedGateway = ref(null);

watch(
    () => props.open,
    (newVal) => {
        if (newVal) {
            selectedGateway.value = null;
            // Hide all iti flag containers when dialog opens
            document.querySelectorAll(".iti__selected-flag, .iti__separate-dial-code, .iti").forEach(el => {
                el.style.visibility = "hidden";
            });
        } else {
            // Show them again when dialog closes
            document.querySelectorAll(".iti__selected-flag, .iti__separate-dial-code, .iti").forEach(el => {
                el.style.visibility = "visible";
            });
        }
    }
);

const closeDialog = () => {
    isOpen.value = false;
    selectedGateway.value = null;
    // Restore phone inputs
    document.querySelectorAll(".iti__selected-flag, .iti__separate-dial-code, .iti").forEach(el => {
        el.style.visibility = "visible";
    });
};

const proceedToPayment = () => {
    if (!selectedGateway.value) return;
    emit("gateway-selected", selectedGateway.value);
    closeDialog();
};
</script>