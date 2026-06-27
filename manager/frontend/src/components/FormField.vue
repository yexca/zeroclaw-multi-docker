<template>
  <label class="form-field" :class="{ 'form-field--wide': wide }">
    <span>{{ label }}</span>
    <textarea v-if="textarea" :value="modelValue" :rows="rows" @input="$emit('update:modelValue', $event.target.value)" />
    <select v-else-if="options.length" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
      <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
    </select>
    <input
      v-else
      :type="type"
      :value="modelValue"
      @input="$emit('update:modelValue', type === 'number' ? Number($event.target.value) : $event.target.value)"
    />
  </label>
</template>

<script setup>
defineEmits(["update:modelValue"]);
defineProps({
  label: { type: String, required: true },
  modelValue: { type: [String, Number, Boolean], default: "" },
  type: { type: String, default: "text" },
  textarea: { type: Boolean, default: false },
  rows: { type: Number, default: 4 },
  wide: { type: Boolean, default: false },
  options: { type: Array, default: () => [] }
});
</script>
