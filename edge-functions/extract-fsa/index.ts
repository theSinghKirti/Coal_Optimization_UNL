// supabase/functions/extract-fsa/index.ts
// Step 6 — FSA AI extraction. Deploy with:
//   supabase functions deploy extract-fsa
// and set the secret:
//   supabase secrets set ANTHROPIC_API_KEY=sk-ant-...
//
// Called from the frontend after a document is uploaded to Storage (Step 4).
// Reads the document text (already OCR'd if it was a scan), asks Claude to
// return typed constraints with clause citations, and inserts them into
// constraints_registry with status='pending' for human review.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY")!;

const EXTRACTION_SYSTEM_PROMPT = `You are extracting structured fuel-supply constraints from an
Indian thermal power plant's coal Fuel Supply Agreement (FSA), Bridge Linkage order, or coal
company order letter. Read the document text and return ONLY a JSON array (no prose, no markdown
fences) where each element is:

{
  "plant": string,
  "company": string,
  "linkage_type": "FSA" | "BRIDGE_LINKAGE",
  "acq_lac_mt": number | null,
  "trigger_level_pct": number | null,
  "take_or_pay_pct": number | null,
  "gcv_band_kcal_kg_min": number | null,
  "gcv_band_kcal_kg_max": number | null,
  "valid_from": "YYYY-MM-DD" | null,
  "valid_to": "YYYY-MM-DD" | null,
  "source_clause": string,        // the exact clause / section reference, e.g. "Clause 4.2"
  "confidence": number            // 0-1, your confidence this value is correctly read
}

If a figure is not present in the document, use null rather than guessing. Never invent a number.`;

Deno.serve(async (req) => {
  try {
    const { document_id } = await req.json();
    if (!document_id) {
      return new Response(JSON.stringify({ error: "document_id required" }), { status: 400 });
    }

    const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

    const { data: doc, error: docErr } = await supabase
      .from("documents")
      .select("*")
      .eq("document_id", document_id)
      .single();
    if (docErr || !doc) {
      return new Response(JSON.stringify({ error: "document not found" }), { status: 404 });
    }

    const { data: fileBlob, error: dlErr } = await supabase.storage
      .from("documents")
      .download(doc.storage_path);
    if (dlErr || !fileBlob) {
      return new Response(JSON.stringify({ error: "could not download file" }), { status: 500 });
    }

    // For scanned PDFs, run OCR (Tesseract/Document AI) upstream of this function
    // and store the resulting text in doc.storage_path + '.txt' instead; this
    // function assumes text-extractable content for clarity.
    const docText = await fileBlob.text();

    const claudeResp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 4000,
        system: EXTRACTION_SYSTEM_PROMPT,
        messages: [
          {
            role: "user",
            content: `Document: ${doc.file_name}\n\n${docText.slice(0, 100_000)}`,
          },
        ],
      }),
    });

    const claudeData = await claudeResp.json();
    const textBlock = claudeData.content?.find((b: any) => b.type === "text");
    if (!textBlock) {
      return new Response(JSON.stringify({ error: "no extraction returned" }), { status: 502 });
    }

    let extracted: any[];
    try {
      extracted = JSON.parse(textBlock.text.trim());
    } catch {
      return new Response(
        JSON.stringify({ error: "extraction was not valid JSON", raw: textBlock.text }),
        { status: 502 }
      );
    }

    const rows = extracted.map((e) => ({
      plant_id: null, // resolved by a lookup against `plants` by name in a follow-up step
      linkage_type: e.linkage_type,
      acq_lac_mt: e.acq_lac_mt,
      trigger_level_pct: e.trigger_level_pct,
      take_or_pay_pct: e.take_or_pay_pct,
      gcv_band_kcal_kg_min: e.gcv_band_kcal_kg_min,
      gcv_band_kcal_kg_max: e.gcv_band_kcal_kg_max,
      valid_from: e.valid_from,
      valid_to: e.valid_to,
      source_document_id: document_id,
      source_clause: e.source_clause,
      extraction_confidence: e.confidence,
      status: "pending",
      // plant / company name strings are kept in a side note for the reviewer
      // until resolved to plant_id / company_id by name match:
      _plant_name: e.plant,
      _company_name: e.company,
    }));

    const { error: insErr } = await supabase.from("constraints_registry").insert(rows);
    if (insErr) {
      return new Response(JSON.stringify({ error: insErr.message }), { status: 500 });
    }

    await supabase.from("audit_log").insert({
      action: "CONSTRAINT_EXTRACTED",
      entity_type: "document",
      entity_id: document_id,
      detail: { count: rows.length, model: "claude-sonnet-4-6" },
    });

    return new Response(JSON.stringify({ inserted: rows.length }), {
      headers: { "content-type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});
