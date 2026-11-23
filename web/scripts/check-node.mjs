/**
 * The web test rig needs the project's pinned Node (see .nvmrc / engines).
 * Without this guard a wrong interpreter dies deep inside undici with
 * "Cannot read properties of undefined (reading 'bind')", because MSW 3
 * pulls undici 8, which binds zlib.createZstdDecompress (Node >= 22.19).
 */
const REQUIRED_MAJOR = 26;
const current = process.versions.node;
const major = Number.parseInt(current.split(".")[0] ?? "", 10);

if (Number.isNaN(major) || major < REQUIRED_MAJOR) {
  console.error(
    [
      `web needs Node ${REQUIRED_MAJOR}+ (running ${current}).`,
      "",
      "  nvm use            # web/.nvmrc pins the right version",
      "  nvm install 26     # only if it is not installed yet",
      "",
      "Older interpreters fail inside undici/MSW with an unrelated-looking",
      "'Cannot read properties of undefined (reading bind)' error.",
    ].join("\n"),
  );
  process.exit(1);
}
