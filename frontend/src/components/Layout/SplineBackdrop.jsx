const SPLINE_SCENE = import.meta.env.VITE_SPLINE_SCENE
  || 'https://my.spline.design/nancylookingaround-cloyfNCxbzM7fwj0IpBuuwzc/';

export default function SplineBackdrop() {
  return (
    <div className="spline-site-backdrop" aria-hidden="true">
      <iframe title="" src={SPLINE_SCENE} tabIndex="-1" />
    </div>
  );
}
