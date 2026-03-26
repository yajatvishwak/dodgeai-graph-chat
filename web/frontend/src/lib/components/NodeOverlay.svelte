<script lang="ts">
  import type { GraphNode } from "$lib/types";

  export let node: GraphNode | null = null;
  export let connectionCount = 0;

  const MAX_FIELDS = 12;

  $: entries = node ? Object.entries(node.properties) : [];
  $: visibleEntries = entries.slice(0, MAX_FIELDS);
  $: hiddenCount = Math.max(entries.length - MAX_FIELDS, 0);
</script>

{#if node}
  <aside class="overlay">
    <h3>{node.label}</h3>
    {#each visibleEntries as [key, value]}
      <div class="row">
        <span class="k">{key}:</span>
        <span class="v">{String(value)}</span>
      </div>
    {/each}
    {#if hiddenCount > 0}
      <p class="meta">Additional fields hidden for readability</p>
    {/if}
    <p class="meta">Connections: {connectionCount}</p>
  </aside>
{/if}

<style>
  .overlay {
    position: absolute;
    top: 24px;
    left: 50%;
    transform: translateX(-50%);
    width: 290px;
    max-height: 72vh;
    overflow: auto;
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 10px 30px rgba(28, 39, 62, 0.2);
    border: 1px solid #e6eaf2;
    padding: 14px 16px;
    z-index: 12;
  }
  h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
    font-weight: 700;
  }
  .row {
    display: flex;
    gap: 8px;
    font-size: 13px;
    margin-bottom: 5px;
  }
  .k {
    font-weight: 600;
    color: #202124;
  }
  .v {
    color: #586173;
    overflow-wrap: anywhere;
  }
  .meta {
    margin: 8px 0 0;
    color: #8b94a5;
    font-style: italic;
    font-size: 12px;
  }
</style>
