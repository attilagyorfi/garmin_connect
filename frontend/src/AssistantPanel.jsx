import { useEffect, useRef, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { Bot, CalendarCheck, Check, Database, Send, Sparkles, Trash2, X } from "lucide-react";
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";

const suggestions = [
  "Mit javasolsz mára az adataim alapján?",
  "Hogyan változott mostanában a terhelésem?",
  "Melyik adat jelzi leginkább, hogy pihenjek?",
];

export function AssistantPanel() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [actionStates, setActionStates] = useState({});
  const saveTimer = useRef(null);
  const { messages, setMessages, sendMessage, status, error } = useChat({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  });
  const busy = status === "submitted" || status === "streaming";
  useEffect(() => {
    let active = true;
    fetch("/api/state", { credentials: "same-origin", cache: "no-store" })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("history")))
      .then((state) => {
        if (!active) return;
        const saved = state.assistant || {};
        setMemoryEnabled(saved.memoryEnabled !== false);
        setMessages((saved.messages || []).map((item) => ({
          id: item.id, role: item.role, parts: [{ type: "text", text: item.text }],
        })));
      })
      .catch(() => {})
      .finally(() => { if (active) setHistoryLoaded(true); });
    return () => { active = false; };
  }, [setMessages]);
  useEffect(() => {
    if (!historyLoaded || status !== "ready") return undefined;
    clearTimeout(saveTimer.current);
    const storedMessages = memoryEnabled ? messages.slice(-40).flatMap((message) => {
      const text = message.parts.filter((part) => part.type === "text").map((part) => part.text).join("\n").trim();
      return text ? [{ id: message.id, role: message.role, text }] : [];
    }) : [];
    saveTimer.current = setTimeout(() => {
      fetch("/api/state", {
        method: "PATCH", credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ assistant: { memoryEnabled, messages: storedMessages } }),
      }).catch(() => {});
    }, 450);
    return () => clearTimeout(saveTimer.current);
  }, [historyLoaded, memoryEnabled, messages, status]);
  const clearHistory = () => {
    setMessages([]);
    fetch("/api/state", {
      method: "PATCH", credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ assistant: { memoryEnabled, messages: [] } }),
    }).catch(() => {});
  };
  const submit = (text) => {
    const value = text.trim();
    if (!value || busy) return;
    sendMessage({ text: value });
    setInput("");
  };
  const decideProposal = async (proposal, decision) => {
    setActionStates((current) => ({ ...current, [proposal.id]: { status: "working" } }));
    try {
      const response = await fetch("/api/assistant-actions", {
        method: "PATCH", credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id: proposal.id, decision }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "A döntés mentése sikertelen.");
      setActionStates((current) => ({ ...current, [proposal.id]: { status: result.status } }));
      if (result.state) window.dispatchEvent(new CustomEvent("hybrid-cloud-state", { detail: result.state }));
    } catch (actionError) {
      setActionStates((current) => ({ ...current, [proposal.id]: { status: "error", error: actionError.message } }));
    }
  };

  return (
    <>
      <button className="assistant-launcher" onClick={() => setOpen(true)} aria-label="AI-asszisztens megnyitása">
        <Sparkles size={20} /><span>Asszisztens</span>
      </button>
      {open && <><div className="assistant-layer-shield" aria-hidden="true" /><aside className="assistant-panel" aria-label="Hybrid Athlete AI-asszisztens">
        <div className="assistant-head">
          <div><span><Bot size={18} /></span><div><strong>Hybrid AI</strong><small>Saját adataid alapján</small></div></div>
          <div className="assistant-head-actions">
            <button onClick={clearHistory} aria-label="Beszélgetés törlése" title="Beszélgetés törlése"><Trash2 size={17} /></button>
            <button onClick={() => setOpen(false)} aria-label="Asszisztens bezárása"><X size={19} /></button>
          </div>
        </div>
        <p className="assistant-privacy">A válaszok a bejelentkezett fiókod szinkronizált adatait használják kontextusként. Ez nem orvosi tanács.</p>
        <label className="assistant-memory"><Database size={14} /><span>Beszélgetési memória</span><input type="checkbox" checked={memoryEnabled} onChange={(event) => setMemoryEnabled(event.target.checked)} /><i aria-hidden="true" /></label>
        <Conversation className="assistant-conversation">
          <ConversationContent className="assistant-messages">
            {messages.length === 0 ? <ConversationEmptyState
              icon={<Sparkles size={24} />}
              title="Miben segíthetek?"
              description="Kérdezz a terhelésedről, regenerációdról vagy fejlődésedről."
            /> : messages.map((message) => <Message from={message.role} key={message.id}>
              <MessageContent>
                {message.parts.filter((part) => part.type === "text").map((part, index) =>
                  <MessageResponse key={index}>{part.text}</MessageResponse>)}
                {message.parts.filter((part) => part.type === "data-plan-proposal").map((part) => {
                  const proposal = part.data;
                  const proposalState = actionStates[proposal.id]?.status || proposal.status;
                  return <section className="assistant-proposal" key={proposal.id} aria-label="Edzésterv-módosítási előnézet">
                    <div><CalendarCheck size={17} /><strong>Jóváhagyásra vár</strong></div>
                    <p>{proposal.summary}</p><small>{proposal.reason}</small>
                    {proposalState === "pending" ? <div className="assistant-proposal-actions">
                      <button onClick={() => decideProposal(proposal, "reject")}><X size={15} /> Elutasítás</button>
                      <button className="approve" onClick={() => decideProposal(proposal, "approve")}><Check size={15} /> Jóváhagyás</button>
                    </div> : proposalState === "working" ? <em>Mentés…</em> : proposalState === "applied" ? <em className="success">Jóváhagyva és alkalmazva.</em> : proposalState === "rejected" ? <em>Elutasítva, nem történt módosítás.</em> : <em className="error">{actionStates[proposal.id]?.error || "A művelet sikertelen."}</em>}
                  </section>;
                })}
              </MessageContent>
            </Message>)}
            {busy && status === "submitted" && <div className="assistant-thinking">Az adataid értelmezése…</div>}
            {error && <div className="assistant-error">Nem sikerült választ kapni. Ellenőrizd az AI Gateway beállítását, majd próbáld újra.</div>}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
        {messages.length === 0 && <div className="assistant-suggestions">
          {suggestions.map((item) => <button key={item} onClick={() => submit(item)}>{item}</button>)}
        </div>}
        <form className="assistant-form" onSubmit={(event) => { event.preventDefault(); submit(input); }}>
          <textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Kérdezz a saját adataidról…" rows={2} onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(input); }
          }} />
          <button type="submit" disabled={!input.trim() || busy} aria-label="Kérdés elküldése"><Send size={17} /></button>
        </form>
      </aside></>}
    </>
  );
}
