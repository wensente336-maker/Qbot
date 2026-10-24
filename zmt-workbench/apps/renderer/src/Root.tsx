import { AbsoluteFill, Composition, Series } from "remotion";
import type { CalculateMetadataFunction } from "remotion";
import { SceneFrame } from "@zmt/visual";

export type Scene = {
  index?: number;
  visual: string;
  subtitle?: string;
  accent?: string;
  /** 分镜时长（帧）。后端按 start_ms / end_ms 换算后写入 */
  durationInFrames?: number;
};

type VideoProps = { scenes?: Scene[] };

const DEFAULT_SCENES: Scene[] = [
  { visual: "开场钩子", subtitle: "3 秒内抓住注意力", accent: "#4da3ff" },
  { visual: "核心论点", subtitle: "一个强观点 + 一个反常识", accent: "#ffb04d" },
  { visual: "情绪递进", subtitle: "制造悬念与共鸣", accent: "#4ade80" },
  { visual: "结尾引导", subtitle: "点赞 · 关注 · 评论", accent: "#ff6b5e" },
];

const FRAMES_PER_SCENE = 90;

function sceneFrames(scene: Scene): number {
  return Math.max(1, scene.durationInFrames ?? FRAMES_PER_SCENE);
}

function totalFrames(scenes: Scene[]): number {
  return Math.max(
    1,
    scenes.reduce((sum, scene) => sum + sceneFrames(scene), 0),
  );
}

export const VideoTemplate: React.FC<VideoProps> = ({
  scenes = DEFAULT_SCENES,
}) => (
  <AbsoluteFill>
    <Series>
      {scenes.map((scene, i) => (
        <Series.Sequence key={i} durationInFrames={sceneFrames(scene)}>
          <SceneFrame
            index={scene.index ?? i + 1}
            visual={scene.visual}
            subtitle={scene.subtitle}
            accent={scene.accent || undefined}
          />
        </Series.Sequence>
      ))}
    </Series>
  </AbsoluteFill>
);

const calculateVideoMetadata: CalculateMetadataFunction<VideoProps> = ({
  props,
}) => ({
  durationInFrames: totalFrames(props.scenes ?? DEFAULT_SCENES),
});

export const RemotionRoot: React.FC = () => (
  <Composition
    id="VideoTemplate"
    component={VideoTemplate}
    durationInFrames={totalFrames(DEFAULT_SCENES)}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{ scenes: DEFAULT_SCENES }}
    calculateMetadata={calculateVideoMetadata}
  />
);
