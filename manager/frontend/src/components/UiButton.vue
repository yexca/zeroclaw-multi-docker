<template>
  <button class="ui-button" :class="[`ui-button--${variant}`, { 'ui-button--icon': icon }]" :type="type">
    <slot />
  </button>
</template>

<script setup>
defineProps({
  variant: { type: String, default: "secondary" },
  type: { type: String, default: "button" },
  icon: { type: Boolean, default: false }
});
</script>
