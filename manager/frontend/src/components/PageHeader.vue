<template>
  <header class="page-header">
    <div>
      <p>{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <span v-if="description">{{ description }}</span>
    </div>
    <div class="page-header__actions">
      <slot />
    </div>
  </header>
</template>

<script setup>
defineProps({
  eyebrow: { type: String, default: "ZeroClaw Dockyard" },
  title: { type: String, required: true },
  description: { type: String, default: "" }
});
</script>
