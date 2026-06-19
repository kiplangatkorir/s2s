declare module "lucide-react" {
  import { ComponentType, SVGAttributes } from "react";
  type IconProps = SVGAttributes<SVGElement> & {
    size?: number | string;
    color?: string;
    strokeWidth?: number | string;
  };
  export const Mic: ComponentType<IconProps>;
  export const MicOff: ComponentType<IconProps>;
  export const Send: ComponentType<IconProps>;
  export const X: ComponentType<IconProps>;
  export const WifiOff: ComponentType<IconProps>;
  export const Volume2: ComponentType<IconProps>;
  export const Copy: ComponentType<IconProps>;
  export const Check: ComponentType<IconProps>;
}
