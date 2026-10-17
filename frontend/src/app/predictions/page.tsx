import type { Metadata } from "next";
import { getPredictions } from "@/lib/vlr";
import { PageContainer } from "@/components/PageContainer";
import { PredictionsBoard } from "@/components/PredictionsBoard";
import "./predictions.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Predictions — valstats" };

export default async function PredictionsPage() {
  const response = await getPredictions();
  const published = response.data.filter(m => m.status === "published").length;
  return <PageContainer width="home"><div className="predictions-page">
    <header className="predictions-masthead"><div><p className="prediction-eyebrow">VALORANT / THE PRE-MATCH READ</p><h1>PREDICTIONS<span>.</span></h1><p className="predictions-deck">One winner. A reason to believe.<br />A clear view of what we don’t know.</p></div><div className="prediction-edition"><span>THE ANALYST’S DESK</span><strong>{published.toString().padStart(2,"0")}</strong><span>saved picks · powered by OpenClaw</span></div></header>
    <div className="predictions-principles"><p><span>01</span> Evidence before instinct.</p><p><span>02</span> Saved before match start.</p><p><span>03</span> No forced picks.</p></div>
    <PredictionsBoard response={response} now={new Date()} />
    <aside className="predictions-method" aria-labelledby="prediction-method"><h2 id="prediction-method">HOW TO READ THE PICK.</h2><p>New analyses compare recent form, verified head-to-head meetings, map results and listed-player statistics when available. The explanation shows the supporting facts and their limits. Picks are saved before the match and remain unchanged afterward.</p><p>This first edition gives a winner lean, without win probabilities or predicted scores. Coverage and sample sizes vary. Historical results cannot confirm player availability, the upcoming map veto or current patch suitability.</p></aside>
  </div></PageContainer>;
}
