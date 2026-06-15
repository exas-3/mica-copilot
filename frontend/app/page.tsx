import { Chat } from "@/components/Chat";

export default function Page() {
  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">Retrieval-augmented · agentic · cited</div>
        <h1>Ask MiCA</h1>
        <p>
          A copilot for the EU Markets in Crypto-Assets Regulation (Regulation (EU) 2023/1114).
          Every answer is grounded in retrieved regulation text and cited by article; the agent can
          also look up the ESMA register snapshot.
        </p>
        <p className="page-credit">
          A final project for the Athens University of Economics and Business (AUEB)
          <em> “AI for Developers — Building with LLMs”</em> course.
        </p>
      </div>
      <Chat />
    </div>
  );
}
