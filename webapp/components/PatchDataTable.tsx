
import React from 'react';
import { YM2612Patch } from '../types';

interface PatchDataTableProps {
  patch: YM2612Patch;
}

export const PatchDataTable: React.FC<PatchDataTableProps> = ({ patch }) => {
  return (
    <div className="w-full bg-[#080808] border border-[#333] rounded-sm p-1 shadow-lg">
      {/* HEADER */}
      <div className="bg-[#111] px-4 py-2 border-b border-[#333] flex justify-between items-center">
        <h3 className="text-[#bc13fe] text-[11px] font-bold tracking-[0.2em] uppercase flex items-center gap-2">
          <span className="w-2 h-2 bg-[#bc13fe] rounded-full shadow-[0_0_5px_#bc13fe]"></span>
          PATCH_DATA // {patch.name}
        </h3>
        <div className="text-[9px] text-white font-mono">YM2612 & YM3438 REGISTER DUMP</div>
      </div>

      <div className="p-4 grid gap-6">
        
        {/* GLOBAL SECTION */}
        <div>
            <div className="text-[10px] text-[#00eaff] font-bold tracking-widest mb-2 border-b border-[#00eaff]/20 pb-1 w-fit">GLOBAL_PARAMETERS</div>
            <div className="grid grid-cols-5 gap-1 text-center">
                {['ALGORITHM', 'FEEDBACK', 'LFO_FREQ', 'AMS', 'FMS'].map(h => (
                    <div key={h} className="bg-[#1a1a1a] py-1 text-[9px] text-white font-bold tracking-wider border border-[#222]">{h}</div>
                ))}
                <div className="bg-black border border-[#333] py-2 text-white font-mono text-sm font-bold">{patch.algorithm}</div>
                <div className="bg-black border border-[#333] py-2 text-white font-mono text-sm font-bold">{patch.feedback}</div>
                <div className="bg-black border border-[#333] py-2 text-white font-mono text-sm font-bold">{patch.lfoFreq}</div>
                <div className="bg-black border border-[#333] py-2 text-white font-mono text-sm font-bold">{patch.ams}</div>
                <div className="bg-black border border-[#333] py-2 text-white font-mono text-sm font-bold">{patch.fms}</div>
            </div>
        </div>

        {/* OPERATOR SECTION */}
        <div>
            <div className="text-[10px] text-[#00eaff] font-bold tracking-widest mb-2 border-b border-[#00eaff]/20 pb-1 w-fit">OPERATOR_CONFIGURATION</div>
            <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                    <thead>
                        <tr>
                            <th className="p-2 text-left bg-[#1a1a1a] text-[9px] text-white border border-[#333] font-bold w-20">PARAM</th>
                            {patch.operators.map((op, i) => (
                                <th key={i} className="p-2 bg-[#111] text-[#bc13fe] border border-[#333] text-[11px] font-bold tracking-wider w-1/4">
                                    OP_{i + 1}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="font-mono text-xs">
                        {[
                            { key: 'mul', label: 'MULTIPLIER (MUL)' },
                            { key: 'tl', label: 'TOTAL LEVEL (TL)' },
                            { key: 'ar', label: 'ATTACK RATE (AR)' },
                            { key: 'dr', label: 'DECAY RATE (DR)' },
                            { key: 'sr', label: 'SUSTAIN RATE (SR)' },
                            { key: 'sl', label: 'SUSTAIN LVL (SL)' },
                            { key: 'rr', label: 'RELEASE RATE (RR)' },
                            { key: 'dt', label: 'DETUNE (DT)' },
                        ].map((row) => (
                            <tr key={row.key}>
                                <td className="p-2 bg-[#0f0f0f] text-white border border-[#222] text-[9px] font-bold tracking-wider">{row.label}</td>
                                {patch.operators.map((op, i) => (
                                    <td key={i} className="p-2 text-center bg-black border border-[#222] text-white font-bold group hover:bg-[#1a1a1a] transition-colors">
                                        {(op as any)[row.key]}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>

      </div>
    </div>
  );
};
