<template>
  <label class="form-field" :class="{ 'form-field--wide': wide, 'form-field--invalid': error }">
    <span>{{ label }}</span>
    <textarea v-if="textarea" :value="modelValue" :rows="rows" :aria-invalid="Boolean(error)" @input="$emit('update:modelValue', $event.target.value)" />
    <select v-else-if="options.length" :value="modelValue" :aria-invalid="Boolean(error)" @change="$emit('update:modelValue', $event.target.value)">
      <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
    </select>
    <input
      v-else
      :type="type"
      :value="modelValue"
      :min="min"
      :max="max"
      :required="required"
      :aria-invalid="Boolean(error)"
      @input="$emit('update:modelValue', type === 'number' && $event.target.value !== '' ? Number($event.target.value) : $event.target.value)"
    />
    <small v-if="error" class="field-error">{{ error }}</small>
  </label>
</template>

<script setup>
defineEmits(["update:modelValue"]);
defineProps({
  label: { type: String, required: true },
  modelValue: { type: [String, Number, Boolean], default: "" },
  type: { type: String, default: "text" },
  min: { type: [String, Number], default: undefined },
  max: { type: [String, Number], default: undefined },
  required: { type: Boolean, default: false },
  textarea: { type: Boolean, default: false },
  rows: { type: Number, default: 4 },
  wide: { type: Boolean, default: false },
  options: { type: Array, default: () => [] },
  error: { type: String, default: "" }
});
</script>
