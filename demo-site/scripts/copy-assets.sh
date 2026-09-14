#!/usr/bin/env bash
# Copy assets from the main Riverst repo into demo-site/public/
# Run from repo root: bash demo-site/scripts/copy-assets.sh
# Or called automatically via the prebuild npm script (which runs from demo-site/).

set -e

# Detect repo root: if running from demo-site/, go up one level
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_SITE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DEMO_SITE_DIR/.." && pwd)"

echo "Copying assets from repo root: $REPO_ROOT"

# Ensure all destination directories exist
mkdir -p "$DEMO_SITE_DIR/src/talkinghead"
mkdir -p "$DEMO_SITE_DIR/public/avatars"
mkdir -p "$DEMO_SITE_DIR/public/logo"
mkdir -p "$DEMO_SITE_DIR/public/screenshots"
mkdir -p "$DEMO_SITE_DIR/public/animations/dance"
mkdir -p "$DEMO_SITE_DIR/public/animations/thinking"

# TalkingHead modules — copied to src/ so Vite bundles them and resolves 'three'
cp "$REPO_ROOT/src/client/react/src/components/avatarInteraction/talkinghead/talkinghead.mjs" \
   "$DEMO_SITE_DIR/src/talkinghead/"
cp "$REPO_ROOT/src/client/react/src/components/avatarInteraction/talkinghead/dynamicbones.mjs" \
   "$DEMO_SITE_DIR/src/talkinghead/"

# playback-worklet.js is required by talkinghead.mjs for audio streaming but is
# not bundled in the Riverst repo. Fetch it from the TalkingHead library.
WORKLET_DST="$DEMO_SITE_DIR/src/talkinghead/playback-worklet.js"
if [ ! -f "$WORKLET_DST" ]; then
  echo "Fetching playback-worklet.js from TalkingHead..."
  curl -fsSL \
    "https://raw.githubusercontent.com/met4citizen/TalkingHead/main/modules/playback-worklet.js" \
    -o "$WORKLET_DST"
fi

# Default avatar
cp "$REPO_ROOT/src/client/react/public/avatars/fabio_avaturn.glb" \
   "$DEMO_SITE_DIR/public/avatars/"

# Riverst logo SVGs
cp "$REPO_ROOT/src/client/react/public/logo/riverst_black.svg" \
   "$DEMO_SITE_DIR/public/logo/"
cp "$REPO_ROOT/src/client/react/public/logo/riverst_white.svg" \
   "$DEMO_SITE_DIR/public/logo/"

# Screenshots
cp "$REPO_ROOT/public/fabio_says_hi.png" "$DEMO_SITE_DIR/public/screenshots/"
cp "$REPO_ROOT/public/session_summary_example.png" "$DEMO_SITE_DIR/public/screenshots/"
cp "$REPO_ROOT/public/automated_audio_analysis.png" "$DEMO_SITE_DIR/public/screenshots/"

# Body animations referenced by demo-widget.js
cp "$REPO_ROOT/src/client/react/public/animations/dance/dance.fbx" \
   "$DEMO_SITE_DIR/public/animations/dance/"
cp "$REPO_ROOT/src/client/react/public/animations/thinking/thinking.fbx" \
   "$DEMO_SITE_DIR/public/animations/thinking/"

echo "Asset copy complete."
