<script lang="ts">
  import ChatPanel from "$lib/components/ChatPanel.svelte";
  import GraphPanel from "$lib/components/GraphPanel.svelte";
  import NodeOverlay from "$lib/components/NodeOverlay.svelte";
  import {
    appendMessage,
    graphData,
    loading,
    messages,
    minimized,
    recentHistoryWindow,
    selectedNodeId,
    statusText
  } from "$lib/stores/chat";
  import type { GraphDataPayload } from "$lib/types";

  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

  $: currentMessages = $messages;
  $: currentGraph = $graphData;
  $: selectedNode = currentGraph.nodes.find((n) => n.id === $selectedNodeId) ?? null;
  $: nodeConnections = selectedNode
    ? currentGraph.edges.filter((e) => e.from === selectedNode.id || e.to === selectedNode.id).length
    : 0;

  async function sendMessage(text: string): Promise<void> {
    appendMessage({ role: "user", content: text });
    loading.set(true);
    try {
      const history = recentHistoryWindow($messages).map((m) => ({
        role: m.role,
        content: m.content
      }));
      const response = await fetch(`${apiBase}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history })
      });
      const data = await response.json();
      const parsed = data?.response ?? {};
      const finalMessage = parsed.message ?? data?.raw ?? "No response";
      appendMessage({
        role: "assistant",
        content: finalMessage,
        cypherQueries: parsed.cypher_queries ?? [],
        confidence: parsed.confidence ?? undefined
      });
      if (data?.graph) {
        graphData.set(data.graph);
      }
    } catch (error) {
      appendMessage({
        role: "assistant",
        content: `Request failed: ${String(error)}`
      });
    } finally {
      loading.set(false);
    }
  }

  function onGraphLoaded(event: CustomEvent<GraphDataPayload>): void {
    graphData.set(event.detail);
  }

  function onSelectNode(event: CustomEvent<{ nodeId: string | null }>): void {
    selectedNodeId.set(event.detail.nodeId);
  }
</script>

<main>
  <section class="toolbar">
    <button on:click={() => minimized.update((v) => !v)}>
      {$minimized ? "Expand" : "Minimize"}
    </button>
  </section>

  <section class="layout">
    <div class="graph">
      <GraphPanel
        graphData={currentGraph}
        minimized={$minimized}
        on:loaded={onGraphLoaded}
        on:selectnode={onSelectNode}
      />
      {#if selectedNode}
        <NodeOverlay node={selectedNode} connectionCount={nodeConnections} />
      {/if}
    </div>
    <div class="chat">
      <ChatPanel
        messages={currentMessages}
        loading={$loading}
        statusText={$statusText}
        on:send={(event) => sendMessage(event.detail.text)}
      />
    </div>
  </section>
</main>

<style>
  main {
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: #f4f6fb;
  }
  .toolbar {
    padding: 14px;
    display: flex;
    gap: 8px;
  }
  .toolbar button {
    border: 1px solid #dce2ee;
    border-radius: 8px;
    padding: 8px 12px;
    background: #fff;
    cursor: pointer;
  }
  .layout {
    flex: 1;
    display: grid;
    grid-template-columns: 65% 35%;
    min-height: 0;
    border-top: 1px solid #e7ebf4;
  }
  .graph,
  .chat {
    min-height: 0;
  }
</style>
