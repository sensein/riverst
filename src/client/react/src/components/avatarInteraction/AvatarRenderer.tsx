// AvatarRenderer.tsx
import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { GLTFLoader } from 'three-stdlib';

interface CameraSettings {
  position: [number, number, number];
  fov?: number;
}

const FULL_BODY_CAMERA_SETTINGS: CameraSettings = {
  position: [0, 1.8, 20],
  fov: 10,
};

const HALF_BODY_CAMERA_SETTINGS: CameraSettings = {
  position: [0, 2.25, 10],
  fov: 10,
};

const HEADSHOT_CAMERA_SETTINGS: CameraSettings = {
  position: [0, 2.6, 2],
  fov: 10,
};

const MAX_IDLE_ANIMATIONS = 1;  // 6

interface AvatarRendererProps {
  cameraType: "full" | "mid" | "upper" | "head";
  avatarUrl: string;
  bodyAnimation?: string | null;
}

const AvatarScene: React.FC<AvatarRendererProps> = ({
    avatarUrl,
    bodyAnimation,
    cameraType,
  }) => {
  const avatarRef = useRef<THREE.Group | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clockRef = useRef(new THREE.Clock());

  const [isLoaded, setIsLoaded] = useState(false);
  const idleActionRef = useRef<THREE.AnimationAction | null>(null);
  const bodyActionRef = useRef<THREE.AnimationAction | null>(null);
  const isBodyPlaying = useRef(false);

  const morphTargetMeshesRef = useRef<{ [key: string]: THREE.Mesh }>({});
  const currentBlendValuesRef = useRef<{ [key: string]: number }>({});

  const interactionState = useRef<null | string>(null);

  const cameraSettings = useMemo(() => {
    switch (cameraType) {
      case 'mid':
        return HALF_BODY_CAMERA_SETTINGS;
      case 'head':
        return HEADSHOT_CAMERA_SETTINGS;
      default:
        return FULL_BODY_CAMERA_SETTINGS;
    }
  }, [cameraType]);

  const loadIdleAnimation = useCallback((custom_number: number | null = null) => {
    const idleNumber = custom_number !== null
      ? String(custom_number).padStart(3, '0')
      : interactionState !== null
      ? '001'
      : String(Math.floor(Math.random() * MAX_IDLE_ANIMATIONS) + 1).padStart(3, '0');
    const idleUrl = `/animations/idle/F_Standing_Idle_${idleNumber}.glb`;
    // console.log('Loading idle animation:', idleNumber);

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
  }, [interactionState]);

  const onAnimationFinished = useCallback((e: { type: string; action: THREE.AnimationAction }) => {
    if (e.action === idleActionRef.current && !isBodyPlaying.current) {
      loadIdleAnimation();
    }

    if (e.action === bodyActionRef.current) {
      isBodyPlaying.current = false;
      bodyActionRef.current = null;

      loadIdleAnimation();
    }
  }, [loadIdleAnimation]);


  useEffect(() => {
    new GLTFLoader().load(avatarUrl, (gltf) => {
      const scene = gltf.scene;

      scene.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
            morphTargetMeshesRef.current[mesh.name] = mesh;
          }
        }
      });
      avatarRef.current = scene;
      mixerRef.current = new THREE.AnimationMixer(gltf.scene);
      mixerRef.current.addEventListener('finished', onAnimationFinished);
      setIsLoaded(true);
    });

    return () => {
      mixerRef.current?.removeEventListener('finished', onAnimationFinished);
    };
  }, [avatarUrl, onAnimationFinished]);

  useEffect(() => {
    if (isLoaded && !isBodyPlaying.current) {
      if (interactionState !== null) {
        // Force interaction idle
        // console.log('[AvatarRenderer] Triggering idle 001 for interaction');
        loadIdleAnimation(1);
      } else {
        // Play random idle only when not interacting
        // console.log('[AvatarRenderer] Triggering random idle');
        loadIdleAnimation();
      }
    }
  }, [isLoaded, interactionState, loadIdleAnimation]);

  const playBodyAnimation = useCallback((type: string) => {
    if (!mixerRef.current) return;
    // console.log("Loading body animation: ", type);

    let animationUrl = '';
    switch (type) {
      case 'dance':
        animationUrl = '/animations/dance/F_Dances_001.glb';
        break;
      case 'wave':
        animationUrl = '/animations/wave/M_Standing_Expressions_001.glb';
        break;
      case 'i_dont_know':
        animationUrl = '/animations/i_dont_know/M_Standing_Expressions_005.glb';
        break;
      case 'idle':
        loadIdleAnimation(1);
        return;
      default:
        console.warn('Animation type not found:', type);
        return;

      // more available animations: https://github.com/readyplayerme/animation-library/tree/master
    }

    new GLTFLoader().load(animationUrl, (gltf) => {
      const clip = gltf.animations[0];
      const newBodyAction = mixerRef.current!.clipAction(clip);

      newBodyAction.setLoop(THREE.LoopOnce, 1);
      newBodyAction.clampWhenFinished = true;
      newBodyAction.reset().play();

      if (idleActionRef.current) {
        idleActionRef.current.crossFadeTo(newBodyAction, 0.5, true);
      } else {
        newBodyAction.fadeIn(0.5);
      }

      bodyActionRef.current = newBodyAction;
      isBodyPlaying.current = true;
    });
  }, [loadIdleAnimation]);

  useEffect(() => {
    if (bodyAnimation) playBodyAnimation(bodyAnimation);
  }, [bodyAnimation, playBodyAnimation]);

  useEffect(() => {
    // This is to fix a glitch when the tab is hidden and then shown again
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // console.log('Tab is visible again — fixing blendshape glitch');

        // Reset delta clock to avoid huge jump
        clockRef.current = new THREE.Clock();

        // Reapply last known blendshape values to prevent visual glitch
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
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  useFrame(() => {
    const delta = clockRef.current.getDelta();

    // Animate avatar
    mixerRef.current?.update(delta);
  });

  return (
    <>
      <PerspectiveCamera makeDefault position={cameraSettings.position} fov={cameraSettings.fov} />

      {/* Background color */}
      <color attach="background" args={['#ececec']} />

      {/* Ambient light to brighten everything uniformly */}
      <ambientLight intensity={1.2} />

      {/* Main directional light (like sunlight) */}
      <directionalLight
        position={[5, 10, 5]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
      />

      {/* Fill light from another direction to soften shadows */}
      <pointLight position={[-5, 5, -5]} intensity={0.4} />

      {/* Optional spotlight for drama */}
      <spotLight
        position={[2, 8, 5]}
        angle={0.4}
        penumbra={0.5}
        intensity={0.8}
        castShadow
      />

      {/* Avatar or fallback box */}
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

const AvatarRenderer: React.FC<AvatarRendererProps> = ({
  avatarUrl,
  bodyAnimation,
  cameraType,
}) => (
  <Canvas shadows gl={{ preserveDrawingBuffer: true }}>
    <React.Suspense fallback={null}>
      <AvatarScene
        avatarUrl={avatarUrl}
        bodyAnimation={bodyAnimation}
        cameraType={cameraType}
      />
    </React.Suspense>
  </Canvas>
);

export default AvatarRenderer;
