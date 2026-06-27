<template>
  <section class="ui-card">
    <header v-if="$slots.title || title" class="ui-card__header">
      <div>
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <slot name="actions" />
    </header>
    <slot />
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, default: "" },
  description: { type: String, default: "" }
});
</script>
