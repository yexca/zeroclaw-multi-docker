<template>
  <div class="json-editor">
    <textarea v-model="draft" spellcheck="false" :aria-invalid="Boolean(error)" @blur="emitValue" />
    <p v-if="error" class="field-error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: [Object, Array, String, Number, Boolean], default: null }
});
const emit = defineEmits(["update:modelValue", "error"]);
const draft = ref(JSON.stringify(props.modelValue ?? {}, null, 2));
const error = ref("");

watch(
  () => props.modelValue,
  (value) => {
    draft.value = JSON.stringify(value ?? {}, null, 2);
  },
  { deep: false }
);

function emitValue() {
  try {
    emit("update:modelValue", JSON.parse(draft.value || "null"));
    error.value = "";
    emit("error", "");
  } catch (exception) {
    error.value = exception.message;
    emit("error", exception.message);
  }
}
</script>
