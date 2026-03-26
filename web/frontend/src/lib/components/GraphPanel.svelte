<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from "svelte";
  import type { GraphDataPayload } from "$lib/types";

  export let graphData: GraphDataPayload = { nodes: [], edges: [] };
  export let minimized = false;

  const dispatch = createEventDispatcher<{
    selectnode: { nodeId: string | null; connectionCount: number };
    loaded: GraphDataPayload;
  }>();

  let container: HTMLDivElement;
  let network: any = null;
  let nodeSet: any = null;
  let edgeSet: any = null;
  let DataSetCtor: any = null;
  let NetworkCtor: any = null;

  const palette: Record<string, string> = {
    Address: "#7cb5ff",
    BillingDocument: "#ff8ab0",
    BillingItem: "#ffb085",
    Customer: "#5aa9ff",
    Delivery: "#4ecdc4",
    DeliveryItem: "#8dd3c7",
    JournalEntry: "#b39ddb",
    Payment: "#ffd166",
    Plant: "#95d5b2",
    Product: "#cdb4db",
    SalesOrder: "#80ed99",
    SalesOrderItem: "#a0c4ff",
    Node: "#94a3b8",
  };

  function toVisNode(node: any) {
    const label =
      node.properties?.fullName ||
      node.properties?.productName ||
      node.properties?.plantName ||
      node.properties?.salesOrderId ||
      node.properties?.billingDocumentId ||
      node.properties?.journalEntryId ||
      node.properties?.paymentId ||
      node.properties?.deliveryId ||
      node.properties?.addressId ||
      node.id;
    return {
      id: node.id,
      label: String(label),
      title: `${node.label}\n${JSON.stringify(node.properties, null, 2)}`,
      group: node.group,
      color: {
        background: palette[node.group] ?? palette.Node,
        border: "#d9deea",
      },
      font: { color: "#1f2937", size: 12 },
      shape: "dot",
      size: 11,
    };
  }

  function toVisEdge(edge: any) {
    return {
      id: edge.id,
      from: edge.from,
      to: edge.to,
      label: edge.label,
      arrows: "to",
      color: { color: "#b9c2d0" },
      font: { size: 10, color: "#7a8597", strokeWidth: 0 },
      smooth: false,
    };
  }

  function setGraph(data: GraphDataPayload): void {
    if (!DataSetCtor || !network) return;
    nodeSet = new DataSetCtor(data.nodes.map(toVisNode));
    edgeSet = new DataSetCtor(data.edges.map(toVisEdge));
    network?.setOptions({ physics: { enabled: true, stabilization: { iterations: 120, fit: true } } });
    network?.setData({ nodes: nodeSet, edges: edgeSet });
  }

  async function loadInitialGraph() {
    const response = await fetch("/api/graph?limit=50");
    if (!response.ok) {
      throw new Error(`Graph API returned ${response.status}`);
    }
    const data = (await response.json()) as GraphDataPayload;
    dispatch("loaded", data);
    setGraph(data);
  }

  onMount(async () => {
    const [{ DataSet }, { Network }] = await Promise.all([
      import("vis-data"),
      import("vis-network"),
    ]);
    DataSetCtor = DataSet;
    NetworkCtor = Network;
    nodeSet = new DataSetCtor([]);
    edgeSet = new DataSetCtor([]);

    network = new NetworkCtor(
      container,
      { nodes: nodeSet, edges: edgeSet },
      {
        autoResize: true,
        interaction: { hover: true, multiselect: false, hideEdgesOnDrag: true },
        physics: {
          enabled: true,
          stabilization: { iterations: 120, fit: true },
          barnesHut: { springLength: 120, damping: 0.5, gravitationalConstant: -3000 },
        },
        nodes: { borderWidth: 1 },
        edges: { width: 1.1, smooth: false },
      },
    );

    network.on("stabilized", () => {
      network?.setOptions({ physics: { enabled: false } });
    });

    network.on("click", (params: { nodes: Array<string | number> }) => {
      const nodeId = params.nodes[0] ? String(params.nodes[0]) : null;
      const connectionCount = nodeId
        ? (network?.getConnectedNodes(nodeId).length ?? 0)
        : 0;
      dispatch("selectnode", { nodeId, connectionCount });
    });

    try {
      await loadInitialGraph();
    } catch (_error) {
      // Keep canvas clean even if backend is unavailable.
    }
  });

  onDestroy(() => {
    network?.destroy();
  });

  $: if (network && graphData) {
    const _track = graphData.nodes.length + graphData.edges.length;
    setGraph(graphData);
  }
</script>

<section class:minimized>
  <div bind:this={container} class="canvas"></div>
</section>

<style>
  section {
    position: relative;
    width: 100%;
    height: 100%;
    border-right: 1px solid #e6eaf2;
    background: radial-gradient(
        circle at 20px 20px,
        #e9edf5 1px,
        transparent 1px
      ),
      #f8f9fc;
    background-size: 28px 28px;
  }
  section.minimized {
    height: 56px;
  }
  .canvas {
    width: 100%;
    height: 100%;
  }
</style>
