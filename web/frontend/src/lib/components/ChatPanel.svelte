<script lang="ts">
  import { afterUpdate, createEventDispatcher } from "svelte";
  import { marked } from "marked";
  import type { ChatMessage } from "$lib/types";

  marked.setOptions({ breaks: true, gfm: true });

  export let messages: ChatMessage[] = [];
  export let loading = false;
  export let statusText = "Dodge AI is awaiting instructions";

  const dispatch = createEventDispatcher<{ send: { text: string } }>();
  let text = "";
  let messagesEl: HTMLDivElement;
  let expandedQueries: Record<number, boolean> = {};

  afterUpdate(() => {
    if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
  });

  function submit() {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    dispatch("send", { text: trimmed });
    text = "";
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function toggleQueries(index: number) {
    expandedQueries[index] = !expandedQueries[index];
    expandedQueries = expandedQueries;
  }

  function renderMarkdown(raw: string): string {
    return marked.parse(raw, { async: false }) as string;
  }

</script>

<aside class="chat">
  <header>
    <h2>Chat with Graph</h2>
    <p>Order to Cash</p>
  </header>

  <div class="agent">
    <div class="avatar">D</div>
    <div>
      <strong>Dodge AI</strong>
      <p>Graph Agent</p>
    </div>
  </div>

  <div class="messages" bind:this={messagesEl}>
    {#each messages as msg, i}
      <div class="line {msg.role}">
        {#if msg.role === "user"}
          <div class="bubble user-bubble">{msg.content}</div>
        {:else}
          <div class="bubble assistant-bubble">
            <div class="rendered">{@html renderMarkdown(msg.content)}</div>

            {#if msg.confidence != null}
              <div class="confidence">
                Confidence: <strong>{Math.round(msg.confidence * 100)}%</strong>
              </div>
            {/if}

            {#if msg.cypherQueries && msg.cypherQueries.length > 0}
              <button class="toggle-queries" on:click={() => toggleQueries(i)}>
                {expandedQueries[i] ? "Hide" : "Show"} Cypher
                ({msg.cypherQueries.length})
              </button>
              {#if expandedQueries[i]}
                <div class="queries">
                  {#each msg.cypherQueries as q, qi}
                    <pre class="cypher"><code>{q}</code></pre>
                  {/each}
                </div>
              {/if}
            {/if}
          </div>
        {/if}
      </div>
    {/each}

    {#if loading}
      <div class="line assistant">
        <div class="bubble assistant-bubble typing">
          <span></span><span></span><span></span>
        </div>
      </div>
    {/if}
  </div>

  <div class="status">
    <span class="dot" class:pulse={loading}></span>
    <span>{statusText}</span>
  </div>

  <div class="composer">
    <textarea
      rows="2"
      placeholder="Analyze anything"
      bind:value={text}
      on:keydown={onKeydown}
      disabled={loading}
    ></textarea>
    <button on:click={submit} disabled={loading}>Send</button>
  </div>
</aside>

<style>
  .chat {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 14px;
    background: #fff;
  }
  header h2 {
    margin: 0;
    font-size: 18px;
  }
  header p {
    margin: 2px 0 12px;
    color: #7f8899;
    font-size: 12px;
  }
  .agent {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
  .avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #111827;
    color: #fff;
    display: grid;
    place-items: center;
    font-weight: 700;
  }
  .agent p {
    margin: 0;
    color: #7f8899;
    font-size: 12px;
  }

  .messages {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 6px 0;
  }
  .line {
    display: flex;
  }
  .line.user {
    justify-content: flex-end;
  }

  .bubble {
    max-width: 92%;
    border-radius: 10px;
    padding: 10px 12px;
    line-height: 1.45;
    font-size: 14px;
  }
  .user-bubble {
    background: #16191f;
    color: #fff;
    white-space: pre-wrap;
  }
  .assistant-bubble {
    background: #f3f5f9;
    color: #1f2937;
  }

  .rendered :global(p) {
    margin: 0 0 6px;
  }
  .rendered :global(h1),
  .rendered :global(h2),
  .rendered :global(h3),
  .rendered :global(h4) {
    margin: 8px 0 4px;
    line-height: 1.3;
  }
  .rendered :global(h1) { font-size: 16px; }
  .rendered :global(h2) { font-size: 15px; }
  .rendered :global(h3) { font-size: 14px; }
  .rendered :global(h4) { font-size: 13px; }
  .rendered :global(ol),
  .rendered :global(ul) {
    margin: 4px 0;
    padding-left: 20px;
  }
  .rendered :global(li) {
    margin-bottom: 3px;
  }
  .rendered :global(strong) {
    font-weight: 600;
  }
  .rendered :global(em) {
    font-style: italic;
  }
  .rendered :global(code) {
    background: #e4e8f0;
    border-radius: 3px;
    padding: 1px 4px;
    font-size: 12px;
    font-family: "SF Mono", Menlo, monospace;
  }
  .rendered :global(pre) {
    background: #1e293b;
    color: #e2e8f0;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 12px;
    overflow-x: auto;
    margin: 6px 0;
  }
  .rendered :global(pre code) {
    background: none;
    padding: 0;
    color: inherit;
  }
  .rendered :global(blockquote) {
    border-left: 3px solid #cbd5e1;
    margin: 6px 0;
    padding: 2px 10px;
    color: #64748b;
  }
  .rendered :global(table) {
    border-collapse: collapse;
    margin: 6px 0;
    font-size: 13px;
    width: 100%;
  }
  .rendered :global(th),
  .rendered :global(td) {
    border: 1px solid #d1d9e6;
    padding: 4px 8px;
    text-align: left;
  }
  .rendered :global(th) {
    background: #e9edf5;
    font-weight: 600;
  }
  .rendered :global(hr) {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 8px 0;
  }

  .confidence {
    margin-top: 6px;
    font-size: 12px;
    color: #5f6b7a;
  }

  .toggle-queries {
    display: inline-block;
    margin-top: 6px;
    background: none;
    border: 1px solid #d0d7e3;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    color: #4b5563;
    cursor: pointer;
  }
  .toggle-queries:hover {
    background: #edf0f6;
  }

  .queries {
    margin-top: 6px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .cypher {
    background: #1e293b;
    color: #e2e8f0;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 12px;
    font-family: "SF Mono", Menlo, monospace;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    margin: 0;
  }
  .cypher code {
    background: none;
    padding: 0;
    color: inherit;
  }

  .typing {
    display: flex;
    gap: 4px;
    align-items: center;
    padding: 12px 16px;
  }
  .typing span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #94a3b8;
    animation: blink 1.2s infinite;
  }
  .typing span:nth-child(2) { animation-delay: 0.2s; }
  .typing span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes blink {
    0%, 80%, 100% { opacity: 0.3; }
    40% { opacity: 1; }
  }

  .status {
    margin: 8px 0;
    border-top: 1px solid #edf1f7;
    padding-top: 8px;
    color: #677084;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #22c55e;
  }
  .dot.pulse {
    animation: pulse 1s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  .composer {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 8px;
    background: #fbfcfe;
  }
  textarea {
    width: 100%;
    border: 0;
    background: transparent;
    resize: none;
    font: inherit;
    outline: none;
  }
  button {
    margin-left: auto;
    display: block;
    border: 0;
    border-radius: 8px;
    padding: 8px 14px;
    color: #fff;
    background: #8f98aa;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.6;
    cursor: default;
  }
</style>
