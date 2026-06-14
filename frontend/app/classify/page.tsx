import { Classify } from "@/components/Classify";

export default function Page() {
  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">Structured output · JSON schema</div>
        <h1>Classify under MiCA</h1>
        <p>
          Describe a token or service and the copilot classifies it (ART / EMT / other crypto-asset
          / out of scope), flags the crypto-asset services involved, and lists the key obligations —
          grounded in retrieved provisions and returned as a structured result.
        </p>
      </div>
      <Classify />
    </div>
  );
}
