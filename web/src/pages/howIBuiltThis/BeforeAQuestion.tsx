import { RUN } from "./run";
import { Part, Section, Tools } from "./Section";

function Documents() {
    return (
        <Section id="rag-the-documents" title="RAG: the documents">
            <p>
                RAG, short for retrieval-augmented generation, means the model answers from
                documents I hand it, not from memory. So first I download Delta Controls' public
                catalog sheets and product pages, one every 10 seconds, the pace its robots.txt
                file asks of bots. That gives {RUN.documents} documents: {RUN.pdfs} PDFs and{" "}
                {RUN.pages} web pages. I turn each one into text and split it at its headings
                into {RUN.sections} sections. Each section is then cut into
                chunks of about 300 tokens, a token being roughly three quarters of a word.
            </p>
            <Tools
                names="httpx, selectolax, Docling with pypdfium2 as a fallback, LlamaIndex"
                code="src/bas_assistant/ingest/"
            />
        </Section>
    );
}

function Embeddings() {
    return (
        <Section id="embeddings" title="Embeddings">
            <p>
                Each chunk then needs a form a computer can compare by meaning. An embedding is
                that form: a list of 1,536 numbers, where chunks about similar things get similar
                numbers. I make one for every chunk with OpenAI's text-embedding-3-small model,
                once, when the documents are loaded. They go into Postgres, the database, with
                pgvector, an add-on that stores these lists and finds the nearest ones. Postgres
                also keeps a word index of every chunk, so a search can still match an exact
                model number like eZNT-T331.
            </p>
            <Tools
                names="OpenAI text-embedding-3-small through LiteLLM, Postgres 16 with pgvector"
                code="src/bas_assistant/retrieval/embeddings.py"
            />
        </Section>
    );
}

export function BeforeAQuestion() {
    return (
        <Part id="step-1" title="Step 1: Before anyone asks a question">
            <Documents />
            <Embeddings />
        </Part>
    );
}
