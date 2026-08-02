import React, { useEffect, useImperativeHandle, useRef, forwardRef } from "react";
import QRCodeStyling from "qr-code-styling";

const QRPreview = forwardRef(function QRPreview({ value, style = {}, size = 220 }, ref) {
  const containerRef = useRef(null);
  const qrRef = useRef(null);

  const options = () => ({
    width: size,
    height: size,
    type: "svg",
    data: value || "https://midgate.io",
    margin: style.margin ?? 8,
    qrOptions: { errorCorrectionLevel: style.error_correction || "M" },
    dotsOptions: { color: style.fg_color || "#0A0A0A", type: style.dots_style || "rounded" },
    backgroundOptions: { color: style.bg_color || "#FFFFFF" },
    cornersSquareOptions: { type: style.corners_style || "extra-rounded", color: style.fg_color || "#0A0A0A" },
    image: style.logo_url || undefined,
    imageOptions: { crossOrigin: "anonymous", margin: 6, imageSize: 0.35 },
  });

  useEffect(() => {
    qrRef.current = new QRCodeStyling(options());
    if (containerRef.current) {
      containerRef.current.innerHTML = "";
      qrRef.current.append(containerRef.current);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size]);

  useEffect(() => {
    if (qrRef.current) qrRef.current.update(options());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, JSON.stringify(style)]);

  useImperativeHandle(ref, () => ({
    download: (extension) => {
      if (qrRef.current) qrRef.current.download({ name: "midgate-qr", extension });
    },
  }));

  return (
    <div
      ref={containerRef}
      data-testid="qr-preview"
      className="flex items-center justify-center rounded-xl border border-border bg-white p-3"
      style={{ width: size + 24, height: size + 24 }}
    />
  );
});

export default QRPreview;
