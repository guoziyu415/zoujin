// The ending's staging must never take the ending down with it: if the 3D staging throws, it is dropped and the
// subtitles go on with the bridge's stand-in (every shot done at once, the card's fallback picture).
import { Component, type ReactNode } from "react";
import { setStageBridge } from "../../ui/ending/stage/bridge";
import { rig } from "../rig";

export class StagingGuard extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  override state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  override componentDidCatch(e: unknown) {
    console.warn("[ending] the 3D staging stopped", e);
    setStageBridge(null);
    rig.stage = null;
    rig.staged = false;
  }
  override render() {
    return this.state.failed ? null : this.props.children;
  }
}
