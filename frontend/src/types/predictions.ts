export type PredictionTeam = { id: string | null; name: string; logo: string | null };
export type PredictionFact = { id: string; teamId: string; text: string; sourceUrl: string };
export type MatchPrediction = {
  matchId: string;
  teams: [PredictionTeam, PredictionTeam];
  event: string | null;
  timing: string | null;
  startsAt: string | null;
  generatedAt: string | null;
  status: "published" | "no_pick" | "pending";
  prediction: { winnerId: string | null; explanation: string; evidenceIds: string[]; caveats: string[] } | null;
  facts: PredictionFact[];
  limitations: string[];
};
