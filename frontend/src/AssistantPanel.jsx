import { useState } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { Bot, Send, Sparkles, X } from "lucide-react";
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
  const { messages, sendMessage, status, error } = useChat({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  });
  const busy = status === "submitted" || status === "streaming";
  const submit = (text) => {
    const value = text.trim();
    if (!value || busy) return;
    sendMessage({ text: value });
    setInput("");
  };

  return (
    <>
      <button className="assistant-launcher" onClick={() => setOpen(true)} aria-label="AI-asszisztens megnyitása">
        <Sparkles size={20} /><span>Asszisztens</span>
      </button>
      {open && <aside className="assistant-panel" aria-label="Hybrid Athlete AI-asszisztens">
        <div className="assistant-head">
          <div><span><Bot size={18} /></span><div><strong>Hybrid AI</strong><small>Saját adataid alapján</small></div></div>
          <button onClick={() => setOpen(false)} aria-label="Asszisztens bezárása"><X size={19} /></button>
        </div>
        <p className="assistant-privacy">A válaszok a bejelentkezett fiókod szinkronizált adatait használják kontextusként. Ez nem orvosi tanács.</p>
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
      </aside>}
    </>
  );
}
