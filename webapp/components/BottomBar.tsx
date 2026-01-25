/**
 * Bottom Bar Component - Oscilloscope and Save/Download button
 */

import React, { useEffect, useRef } from 'react';

interface BottomBarProps {
  analyser: AnalyserNode | null;
  onDownload: () => void;
  isDownloading: boolean;
}

export const BottomBar: React.FC<BottomBarProps> = ({
  analyser,
  onDownload,
  isDownloading,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();

  useEffect(() => {
    if (!analyser || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animationFrameRef.current = requestAnimationFrame(draw);
      
      analyser.getByteTimeDomainData(dataArray);
      
      ctx.fillStyle = '#050505';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#00eaff';
      ctx.beginPath();
      
      const sliceWidth = canvas.width / bufferLength;
      let x = 0;
      
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;
        
        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
        
        x += sliceWidth;
      }
      
      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
    };

    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    draw();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [analyser]);

  return (
    <div className="flex gap-4 items-stretch h-[100px] bg-[#080808]/95 border border-[#222] rounded-lg p-2">
      {/* Oscilloscope */}
      <div className="flex-1 relative bg-[#050505] border border-[#222] rounded overflow-hidden group">
        <div className="absolute top-1 left-2 text-[7px] text-[#00eaff] tracking-widest z-10 bg-black/50 px-1 rounded uppercase">
          Oscilloscope
        </div>
        <canvas 
          ref={canvasRef}
          className="w-full h-full opacity-90 group-hover:opacity-100 transition-opacity" 
        />
      </div>

      {/* Save to Memory / Download Button */}
      <button
        onClick={onDownload}
        disabled={isDownloading}
        className={`w-48 flex flex-col items-center justify-center gap-2 border rounded transition-all ${
          isDownloading 
            ? 'bg-[#111] border-[#333] cursor-not-allowed'
            : 'bg-[#111] border-kasser-blue/50 hover:bg-kasser-blue hover:border-kasser-blue hover:shadow-[0_0_20px_rgba(0,234,255,0.3)] group'
        }`}
      >
        {isDownloading ? (
          <>
            <div className="w-6 h-6 border-2 border-kasser-blue border-t-transparent rounded-full animate-spin" />
            <span className="text-[10px] text-gray-400 uppercase tracking-wider">Compressing...</span>
          </>
        ) : (
          <>
            <svg 
              className="w-6 h-6 text-kasser-blue group-hover:text-black transition-colors" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" 
              />
            </svg>
            <div className="flex flex-col items-center">
              <span className="text-[10px] text-kasser-blue group-hover:text-black uppercase tracking-wider font-bold transition-colors">
                Save to Memory
              </span>
              <span className="text-[8px] text-gray-500 group-hover:text-black/60 transition-colors">
                Download 6 Slots as ZIP
              </span>
            </div>
          </>
        )}
      </button>
    </div>
  );
};
