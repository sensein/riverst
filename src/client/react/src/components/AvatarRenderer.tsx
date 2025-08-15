/**
 * AvatarRenderer.tsx
 * Renders a 3D avatar using react-three-fiber and three.js.
 * - Loads avatar GLTF model
 * - Plays idle animation
 * - Adjusts camera based on the selected view (full, mid, head)
 * - Handles tab visibility switch for glitch fix
 */

import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
} from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { GLTFLoader } from 'three-stdlib';

interface AvatarRendererProps {
  cameraType: 'full' | 'mid' | 'upper' | 'head';
  avatarUrl: string;
}

interface CameraSettings {
  position: [number, number, number];
  fov?: number;
}

// Camera presets
const CAMERA_PRESETS: Record<string, CameraSettings> = {
  full: { position: [0, 1.8, 20], fov: 10 },
  mid: { position: [0, 2.25, 10], fov: 10 },
  upper: { position: [0, 2.25, 10], fov: 10 },
  head: { position: [0, 2.6, 2], fov: 10 },
};

const MAX_IDLE_ANIMATIONS = 6;

const AvatarScene: React.FC<AvatarRendererProps> = ({
  avatarUrl,
  cameraType,
}) => {
  const avatarRef = useRef<THREE.Group | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clockRef = useRef(new THREE.Clock());

  const [isLoaded, setIsLoaded] = useState(false);
  const idleActionRef = useRef<THREE.AnimationAction | null>(null);

  const morphTargetMeshesRef = useRef<{ [key: string]: THREE.Mesh }>({});
  const currentBlendValuesRef = useRef<{ [key: string]: number }>({});

  const cameraSettings = useMemo(
    () => CAMERA_PRESETS[cameraType] || CAMERA_PRESETS['full'],
    [cameraType]
  );

  const loadIdleAnimation = useCallback(() => {
    const idleNumber = String(Math.floor(Math.random() * MAX_IDLE_ANIMATIONS) + 1).padStart(3, '0');

    const idleUrl = `/animations/idle/F_Standing_Idle_${idleNumber}.glb`;

    new GLTFLoader().load(idleUrl, (gltf) => {
      if (!mixerRef.current) return;
      const clip = gltf.animations[0];
      const newIdleAction = mixerRef.current.clipAction(clip);

      newIdleAction.setLoop(THREE.LoopOnce, 1);
      newIdleAction.clampWhenFinished = true;
      newIdleAction.reset().play();

      if (idleActionRef.current) {
        idleActionRef.current.crossFadeTo(newIdleAction, 0.5, true);
      } else {
        newIdleAction.fadeIn(0.5);
      }

      idleActionRef.current = newIdleAction;
    });
  }, []);

  const onAnimationFinished = useCallback((e: { action: THREE.AnimationAction }) => {
    if (e.action === idleActionRef.current) {
      loadIdleAnimation();
    }
  }, [loadIdleAnimation]);

  useEffect(() => {
    new GLTFLoader().load(avatarUrl, (gltf) => {
      const scene = gltf.scene;

      // Cache morph targets (blendshapes)
      scene.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
            morphTargetMeshesRef.current[mesh.name] = mesh;
          }
        }
      });

      avatarRef.current = scene;
      mixerRef.current = new THREE.AnimationMixer(scene);
      mixerRef.current.addEventListener('finished', onAnimationFinished);
      setIsLoaded(true);
    });

    return () => {
      mixerRef.current?.removeEventListener('finished', onAnimationFinished);
    };
  }, [avatarUrl, onAnimationFinished]);

  useEffect(() => {
    if (isLoaded) {
      loadIdleAnimation(); // Default to idle 001
    }
  }, [isLoaded, loadIdleAnimation]);

  // Fix blendshape glitch when tab is hidden and re-shown
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        clockRef.current = new THREE.Clock(); // reset delta clock
        Object.values(morphTargetMeshesRef.current).forEach((mesh) => {
          const dict = mesh.morphTargetDictionary!;
          const influences = mesh.morphTargetInfluences!;
          Object.keys(dict).forEach((shape) => {
            const index = dict[shape];
            if (index !== undefined) {
              influences[index] = currentBlendValuesRef.current[shape] || 0;
            }
          });
        });
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () =>
      document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  useFrame(() => {
    const delta = clockRef.current.getDelta();
    mixerRef.current?.update(delta);
  });

  return (
    <>
      <PerspectiveCamera makeDefault position={cameraSettings.position} fov={cameraSettings.fov} />

      {/* Lighting and background */}
      <color attach="background" args={['#ececec']} />
      <ambientLight intensity={1.2} />
      <directionalLight
        position={[5, 10, 5]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
      />
      <pointLight position={[-5, 5, -5]} intensity={0.4} />
      <spotLight
        position={[2, 8, 5]}
        angle={0.4}
        penumbra={0.5}
        intensity={0.8}
        castShadow
      />

      {/* Render avatar or fallback */}
      {isLoaded && avatarRef.current ? (
        <primitive object={avatarRef.current} scale={1.6} position={[0, 0, -2.5]} />
      ) : (
        <mesh>
          <boxGeometry args={[0.2, 0.2, 0.2]} />
          <meshStandardMaterial color="red" />
        </mesh>
      )}
    </>
  );
};

const AvatarRenderer: React.FC<AvatarRendererProps> = ({ avatarUrl, cameraType }) => (
  <Canvas shadows gl={{ preserveDrawingBuffer: true }}>
    <React.Suspense fallback={null}>
      <AvatarScene avatarUrl={avatarUrl} cameraType={cameraType} />
    </React.Suspense>
  </Canvas>
);

export default AvatarRenderer;
