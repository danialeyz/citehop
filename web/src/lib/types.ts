/* Generated from design/contracts/search-view.schema.json by npm run gen:types. Do not edit. */

/**
 * Presentation adapter contract, not an existing API or raw LitSearch mapping.
 */
export interface ProposedCiteHopSearchPresentationModel {
  query: string;
  method: "keyword" | "vector" | "fused" | "citehop";
  /**
   * @maxItems 20
   */
  results: {
    paper: {
      corpusid: string;
      title: string;
      abstract: string | null;
      year: number | null;
      n_cited_by: number | null;
      authors: {
        author_id: string;
        name: string;
        position: number;
      }[];
      venue: null | {
        venue_id: number;
        name: string;
      };
    };
    rank: number;
    score: number | null;
    found_via: ("kw" | "vec" | "cite" | "concept" | "author")[];
    graph_only: boolean | null;
    explanation: {
      score_definition: string | null;
      contributions: {
        [k: string]: number;
      } | null;
      paths:
        | {
            nodes: string[];
            edges: {
              source: string;
              target: string;
              relation: string;
            }[];
          }[]
        | null;
    };
  }[];
  returned_count: number;
  latency_ms: number | null;
  partial: boolean;
  unavailable_methods: ("keyword" | "vector" | "fused" | "citehop")[];
}
