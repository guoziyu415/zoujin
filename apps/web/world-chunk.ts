// Match paths inside the module, never directory names in the checkout root.
// In particular, /home/runner is not the reader's home scene.
export function isWorldModule(id: string): boolean {
  const normalized = id.replaceAll("\\", "/");
  if (
    /\/node_modules\/(three|@react-three\/[^/]+|suspend-react|its-fine|react-use-measure|zustand\/esm\/traditional|use-sync-external-store)/.test(
      normalized,
    )
  ) {
    return !/libs\/basis|examples\/jsm\/(?:postprocessing\/GTAOPass|shaders\/(?:GTAOShader|PoissonDenoiseShader)|math\/SimplexNoise|environments\/RoomEnvironment|geometries\/RoundedBoxGeometry)/.test(
      normalized,
    );
  }
  const source = normalized.match(/\/src\/three\/(.*)$/)?.[1];
  return (
    source !== undefined &&
    !/^(?:scene\/(?:extra|land|clouds|prefetch)|quality\/probe|(?:water|dev|castle|road|home)\/|cast\/CastBody|ending\/(?!Guard)|crowd\/(?!presence))/.test(
      source,
    )
  );
}
