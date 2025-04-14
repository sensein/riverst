/*
  Notes for lip sync:
    - https://docs.readyplayer.me/ready-player-me/api-reference/avatars/morph-targets/apple-arkit
    - https://docs.readyplayer.me/ready-player-me/api-reference/avatars/morph-targets/oculus-ovr-libsync
    - https://readyplayer.me/developers/video-tutorials/face-animations-generated-from-audio-with-oculus-lipsync
    - https://community.openai.com/t/how-to-implement-real-time-lip-sync-of-avatar-chatbot-powered-by-gpt/534035/10
    - https://github.com/pipecat-ai/pipecat/issues/1516
*/

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { Html } from '@react-three/drei';

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

const MAX_IDLE_ANIMATIONS = 6;


// Blend shapes that trigger teeth movement
const teethMovingVisemes = ['viseme_aa', 'viseme_E', 'viseme_I', 'viseme_O', 'viseme_U'];

// List of all available blend shape IDs (non‑teeth meshes)
const blendShapeIntensities: { [key: string]: number } = {
  'viseme_sil': 0.6,
  'viseme_PP': 0.6,
  'viseme_FF': 0.6,
  'viseme_TH': 0.6,
  'viseme_DD': 0.6,
  'viseme_kk': 0.6,
  'viseme_CH': 0.6,
  'viseme_SS': 0.6,
  'viseme_nn': 0.6,
  'viseme_RR': 0.6,
  'viseme_aa': 0.4,
  'viseme_E': 0.4,
  'viseme_I': 0.4,
  'viseme_O': 0.4,
  'viseme_U': 0.4
};

const numberToBlendShape: { [key: number]: string } = {
  0: 'viseme_sil',
  1: 'viseme_E',
  2: 'viseme_aa',
  3: 'viseme_O',
  4: 'viseme_E',
  5: 'viseme_RR',
  6: 'viseme_I',
  7: 'viseme_U',
  8: 'viseme_O',
  9: 'viseme_aa',
  10: 'viseme_O',
  11: 'viseme_I',
  12: 'viseme_sil',
  13: 'viseme_RR',
  14: 'viseme_nn',
  15: 'viseme_SS',
  16: 'viseme_CH',
  17: 'viseme_TH',
  18: 'viseme_FF',
  19: 'viseme_DD',
  20: 'viseme_kk',
  21: 'viseme_PP'
};

interface AvatarRendererProps {
  cameraType: 'full_body' | 'half_body' | 'headshot';
  avatarUrl: string;
  bodyAnimation?: string | null;
  onAnimationEnd?: () => void;
  currentViseme?: number | null;
}

const AvatarScene: React.FC<AvatarRendererProps> = ({ 
    avatarUrl, 
    bodyAnimation, 
    onAnimationEnd,
    cameraType,
    currentViseme
  }) => {
  const avatarRef = useRef<THREE.Group | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clockRef = useRef(new THREE.Clock());

  const [isLoaded, setIsLoaded] = useState(false);
  const idleActionRef = useRef<THREE.AnimationAction | null>(null);
  const bodyActionRef = useRef<THREE.AnimationAction | null>(null);
  const currentIdleRef = useRef(1);
  const isBodyPlaying = useRef(false);

  const morphTargetMeshesRef = useRef<{ [key: string]: THREE.Mesh }>({});
  const currentBlendValuesRef = useRef<{ [key: string]: number }>({});
  const targetBlendValuesRef = useRef<{ [key: string]: number }>({});

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

  function sanitizeAnimationClip(
    clip: THREE.AnimationClip,
    avatar: THREE.Group
  ): THREE.AnimationClip {
    const existingBoneNames = new Set<string>();
    avatar.traverse((obj) => {
      if (obj.name) existingBoneNames.add(obj.name);
    });
  
    const filteredTracks = clip.tracks.filter((track) => {
      const nodeName = track.name.split('.')[0];
      return existingBoneNames.has(nodeName);
    });
  
    return new THREE.AnimationClip(clip.name, clip.duration, filteredTracks);
  }
  

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
  }, [avatarUrl]);

  useEffect(() => {
    if (currentViseme === null) return;
  
    const visemeName = numberToBlendShape[currentViseme];
    const isTeethMoving = teethMovingVisemes.includes(visemeName);
  
    // Update target blendshape values
    Object.keys(blendShapeIntensities).forEach((shape) => {
      const intensity = blendShapeIntensities[shape] ?? 0.5;
      targetBlendValuesRef.current[shape] = visemeName === shape ? intensity : 0;
      // targetBlendValuesRef.current[shape] = visemeName === shape ? 0.6 : 0;
    });
  
    // Control mouthOpen for teeth
    targetBlendValuesRef.current['mouthOpen'] = isTeethMoving ? 1 : 0;
  }, [currentViseme]);
    
  

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
      case 'wave':
        animationUrl = '/animations/wave/M_Standing_Expressions_001.glb';
        break;
      case 'i_dont_know':
        animationUrl = '/animations/i_dont_know/M_Standing_Expressions_005.glb';
        break;
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

  useFrame(() => {
    const delta = clockRef.current.getDelta();
  
    // Animate avatar
    mixerRef.current?.update(delta);
  
    // Interpolate viseme blendshapes
    Object.entries(morphTargetMeshesRef.current).forEach(([meshName, mesh]) => {
      const dict = mesh.morphTargetDictionary!;
      const influences = mesh.morphTargetInfluences!;
  
      Object.keys(targetBlendValuesRef.current).forEach((shape) => {
        const index = dict[shape];
        if (index === undefined) return;
  
        const target = targetBlendValuesRef.current[shape] || 0;
        const current = currentBlendValuesRef.current[shape] || 0;
  
        const newVal = THREE.MathUtils.lerp(current, target, delta * 5);
        currentBlendValuesRef.current[shape] = newVal;
        influences[index] = newVal;
      });
    });
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
        intensity={1}
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

      {/* Ground plane with soft white material 
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1, 0]} receiveShadow>
          <planeGeometry args={[10, 10]} />
          <meshStandardMaterial color="#ffffff" />
        </mesh>
      */}

      {/* 
        {currentViseme !== null && (
          <Html position={[0.5, 2.5, -2.5]}>
            <div style={{ background: 'white', padding: '4px 8px', borderRadius: '8px', fontSize: '16px', fontWeight: 'bold' }}>
              Viseme: {currentViseme}
            </div>
          </Html>
        )}
      */}
    </>
  );
};

const AvatarRenderer: React.FC<AvatarRendererProps> = ({
  avatarUrl,
  bodyAnimation,
  onAnimationEnd,
  cameraType,
  currentViseme
}) => (
  <Canvas shadows>
    <React.Suspense fallback={null}>
      <AvatarScene
        avatarUrl={avatarUrl}
        bodyAnimation={bodyAnimation}
        onAnimationEnd={onAnimationEnd}
        cameraType={cameraType}
        currentViseme={currentViseme}
      />
    </React.Suspense>
  </Canvas>
);

export default AvatarRenderer;
