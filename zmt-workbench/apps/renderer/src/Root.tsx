import { AbsoluteFill, Composition, Series } from "remotion";
import { SceneFrame } from "@zmt/visual";

type Scene = {
  visual: string;
  subtitle?: string;
  accent?: string;
};

const DEFAULT_SCENES: Scene[] = [
  { visual: "开场钩子", subtitle: "3 秒内抓住注意力", accent: "#4da3ff" },
  { visual: "核心论点", subtitle: "一个强观点 + 一个反常识", accent: "#ffb04d" },
  { visual: "情绪递进", subtitle: "制造悬念与共鸣", accent: "#4ade80" },
  { visual: "结尾引导", subtitle: "点赞 · 关注 · 评论", accent: "#ff6b5e" },
];

const FRAMES_PER_SCENE = 90;

export const VideoTemplate: React.FC<{ scenes?: Scene[] }> = ({
  scenes = DEFAULT_SCENES,
}) => (
  <AbsoluteFill>
    <Series>
      {scenes.map((s, i) => (
        <Series.Sequence key={i} durationInFrames={FRAMES_PER_SCENE}>
          <SceneFrame
            index={i + 1}
            visual={s.visual}
            subtitle={s.subtitle}
            accent={s.accent}
          />
        </Series.Sequence>
      ))}
    </Series>
  </AbsoluteFill>
);

export const RemotionRoot: React.FC = () => (
  <Composition
    id="VideoTemplate"
    component={VideoTemplate}
    durationInFrames={DEFAULT_SCENES.length * FRAMES_PER_SCENE}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{ scenes: DEFAULT_SCENES }}
  />
);