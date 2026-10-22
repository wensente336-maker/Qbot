import { Composition } from "remotion";

// S0 占位：仅注册一个基础 Composition，验证 Remotion 集成；视频制作在 S3 阶段完善。
const Placeholder: React.FC = () => (
  <div style={{ color: "white", fontSize: 48 }}>ZMT Renderer</div>
);

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Placeholder"
      component={Placeholder}
      durationInFrames={30}
      fps={30}
      width={1080}
      height={1920}
    />
  );
};