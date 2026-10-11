// The ending (frontend-design 5): a placeholder until the ending card (M2) — GET …/ending and its 202 wait come then.
import { navigate } from "../app/router";
import { copy } from "../ui/copy";

export default function EndingScreen() {
  return (
    <main className="screen">
      <h1>{copy["ending.world"]}</h1>
      <button className="secondary" onClick={() => navigate("/")}>
        {copy["common.close"]}
      </button>
    </main>
  );
}
