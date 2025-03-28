import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';

interface CameraSettings {
  position: [number, number, number];
  fov?: number;
}

const FULL_BODY_CAMERA_SETTINGS: CameraSettings = {
  position: [0, 1.4, 2],
  fov: 40,
};

const HALF_BODY_CAMERA_SETTINGS: CameraSettings = {
  position: [0, 2, 0],
  fov: 40,
};

const HEADSHOT_CAMERA_SETTINGS: CameraSettings = {
  position: [0, 2.5, -1],
  fov: 40,
};

const MAX_IDLE_ANIMATIONS = 10;

interface AvatarRendererProps {
  cameraType: 'full_body' | 'half_body' | 'headshot';
  avatarUrl: string;
  bodyAnimation?: string | null;
  onAnimationEnd?: () => void;
}

const AvatarScene: React.FC<AvatarRendererProps> = ({ 
    avatarUrl, 
    bodyAnimation, 
    onAnimationEnd,
    cameraType
  }) => {
  const avatarRef = useRef<THREE.Group | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clockRef = useRef(new THREE.Clock());

  const [isLoaded, setIsLoaded] = useState(false);
  const idleActionRef = useRef<THREE.AnimationAction | null>(null);
  const bodyActionRef = useRef<THREE.AnimationAction | null>(null);
  const currentIdleRef = useRef(1);
  const isBodyPlaying = useRef(false);

  const cameraSettings = useMemo(() => {
    switch (cameraType) {
      case 'half_body':
        return HALF_BODY_CAMERA_SETTINGS;
      case 'headshot':
        return HEADSHOT_CAMERA_SETTINGS;
      default:
        return FULL_BODY_CAMERA_SETTINGS;
    }
  }, [cameraType]);

  useEffect(() => {
    new GLTFLoader().load(avatarUrl, (gltf) => {
      avatarRef.current = gltf.scene;
      mixerRef.current = new THREE.AnimationMixer(gltf.scene);
      mixerRef.current.addEventListener('finished', onAnimationFinished);
      setIsLoaded(true);
    });

    return () => {
      mixerRef.current?.removeEventListener('finished', onAnimationFinished);
    };
  }, [avatarUrl]);

  const loadIdleAnimation = useCallback(() => {
    const idleNumber = String(currentIdleRef.current).padStart(3, '0');
    const idleUrl = `/animations/idle/F_Standing_Idle_${idleNumber}.glb`;

    console.log('Loading idle animation:', idleNumber);

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

  useEffect(() => {
    if (isLoaded && !isBodyPlaying.current) loadIdleAnimation();
  }, [isLoaded, loadIdleAnimation]);

  const playBodyAnimation = useCallback((type: string) => {
    if (!mixerRef.current) return;
    console.log("Loading body animation: ", type);

    let animationUrl = '';
    switch (type) {
      case 'dance':
        animationUrl = '/animations/dance/F_Dances_001.glb';
        break;
      default:
        console.warn('Animation type not found:', type);
        return;
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
  }, []);

  useEffect(() => {
    if (bodyAnimation) playBodyAnimation(bodyAnimation);
  }, [bodyAnimation, playBodyAnimation]);

  const onAnimationFinished = useCallback((e: THREE.Event) => {
    if (e.action === idleActionRef.current && !isBodyPlaying.current) {
      currentIdleRef.current = Math.floor(Math.random() * MAX_IDLE_ANIMATIONS) + 1;

      loadIdleAnimation();
    }

    if (e.action === bodyActionRef.current) {
      isBodyPlaying.current = false;
      bodyActionRef.current = null;

      currentIdleRef.current = Math.floor(Math.random() * MAX_IDLE_ANIMATIONS) + 1;
      loadIdleAnimation();

      if (onAnimationEnd) onAnimationEnd();
    }
  }, [loadIdleAnimation, onAnimationEnd]);

  useFrame(() => mixerRef.current?.update(clockRef.current.getDelta()));

  return (
    <>
      <PerspectiveCamera makeDefault position={cameraSettings.position} fov={cameraSettings.fov} />
      <color attach="background" args={['#ececec']} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 10, 5]} intensity={0.8} castShadow />
      {isLoaded && avatarRef.current ? (
        <primitive object={avatarRef.current} scale={1.6} position={[0, 0, -2.5]} />
      ) : (
        <mesh>
          <boxGeometry args={[0.2, 0.2, 0.2]} />
          <meshStandardMaterial color="red" />
        </mesh>
      )}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1, 0]} receiveShadow>
        <planeGeometry args={[10, 10]} />
        <shadowMaterial opacity={0.3} />
      </mesh>
      <Environment preset="city" />
    </>
  );
};

const AvatarRenderer: React.FC<AvatarRendererProps> = ({ avatarUrl, bodyAnimation, onAnimationEnd, cameraType }) => (
  <Canvas shadows>
    <React.Suspense fallback={null}>
      <AvatarScene 
        avatarUrl={avatarUrl} 
        bodyAnimation={bodyAnimation} 
        onAnimationEnd={onAnimationEnd}
        cameraType={cameraType} />
    </React.Suspense>
  </Canvas>
);

export default AvatarRenderer;
