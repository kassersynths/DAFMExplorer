
import { YM2612Patch, DEFAULT_PATCH } from '../../types';
import { YM2612 } from './ym2612_core';

const CLOCK_SPEED = 7670448; 
const BUFFER_SIZE = 4096; // Increased buffer for stability
const MAX_CHANNELS = 6;

// Mapping standard Op order (1,2,3,4) to YM2612 register offsets (0x30, 0x38, 0x34, 0x3C)
// Logical Op 0 -> YM Slot 1 (Reg +0)
// Logical Op 1 -> YM Slot 3 (Reg +8) 
// Logical Op 2 -> YM Slot 2 (Reg +4)
// Logical Op 3 -> YM Slot 4 (Reg +12)
const OP_REG_OFFSETS = [0x00, 0x08, 0x04, 0x0C];

export class AudioEngine {
    ctx: AudioContext;
    scriptNode: ScriptProcessorNode;
    analyser: AnalyserNode;
    gainNode: GainNode;
    ym2612: any;
    
    channels: { note: number; active: boolean }[];
    currentPatch: YM2612Patch;
    nextChannelIdx: number = 0;

    constructor() {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        this.ctx = new AudioContextClass();
        
        // Initialize Emulator
        this.ym2612 = new (YM2612 as any)();
        this.ym2612.init(CLOCK_SPEED, this.ctx.sampleRate);
        this.ym2612.reset();
        this.ym2612.config(14); // 14-bit DAC precision

        this.channels = Array(MAX_CHANNELS).fill(null).map(() => ({ note: -1, active: false }));
        this.currentPatch = DEFAULT_PATCH;

        // Audio Chain
        this.scriptNode = this.ctx.createScriptProcessor(BUFFER_SIZE, 0, 2);
        this.gainNode = this.ctx.createGain();
        this.analyser = this.ctx.createAnalyser();
        
        this.gainNode.gain.value = 1.0; // Max volume
        this.analyser.fftSize = 2048;

        this.scriptNode.onaudioprocess = (e) => this.processAudio(e);

        this.scriptNode.connect(this.gainNode);
        this.gainNode.connect(this.analyser);
        this.analyser.connect(this.ctx.destination);

        // Force initial patch load
        this.setPatch(DEFAULT_PATCH);
        
        console.log("GENESIS AUDIO ENGINE INITIALIZED");
    }

    private write(addr: number, val: number) {
        // Force integers for the emulator
        this.ym2612.write(Math.floor(addr), Math.floor(val));
    }

    setPatch(patch: YM2612Patch) {
        this.currentPatch = patch;
        for (let i = 0; i < MAX_CHANNELS; i++) {
            this.writePatchToChannel(i, patch);
        }
    }

    writePatchToChannel(ch: number, patch: YM2612Patch) {
        const part = ch < 3 ? 0 : 1;
        const addrOffset = part === 1 ? 0x100 : 0;
        const chIdx = ch % 3; // 0, 1, 2

        // 1. Algorithm & Feedback (0xB0)
        const valB0 = ((patch.feedback & 0x7) << 3) | (patch.algorithm & 0x7);
        this.write(addrOffset + 0xB0 + chIdx, valB0);

        // 2. Stereo L/R & AMS & FMS (0xB4)
        // Enable L+R (0xC0) + AMS shift + FMS
        const valB4 = 0xC0 | ((patch.ams & 0x3) << 4) | (patch.fms & 0x7);
        this.write(addrOffset + 0xB4 + chIdx, valB4);

        // 3. Operators
        patch.operators.forEach((op, i) => {
            const opRegOffset = OP_REG_OFFSETS[i];
            const base = addrOffset + chIdx;

            // DT / MUL (0x30)
            this.write(base + 0x30 + opRegOffset, ((op.dt & 7) << 4) | (op.mul & 15));

            // TL (0x40)
            this.write(base + 0x40 + opRegOffset, op.tl & 127);

            // KS / AR (0x50)
            // KS (Bits 6-7) assumed 0 or from patch if available. AR (0-31)
            const ks = (op.rs || 0) << 6; 
            this.write(base + 0x50 + opRegOffset, ks | (op.ar & 31));

            // AM / DR (0x60)
            const am = op.ams ? 0x80 : 0;
            this.write(base + 0x60 + opRegOffset, am | (op.dr & 31));

            // SR (0x70)
            this.write(base + 0x70 + opRegOffset, op.sr & 31);

            // SL / RR (0x80)
            this.write(base + 0x80 + opRegOffset, ((op.sl & 15) << 4) | (op.rr & 15));
            
            // SSG-EG (0x90) - Disable
            this.write(base + 0x90 + opRegOffset, 0x00);
        });
    }

    noteOn(note: number) {
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }

        // Round-robin allocation
        const chIndex = this.nextChannelIdx;
        this.nextChannelIdx = (this.nextChannelIdx + 1) % MAX_CHANNELS;
        
        const ch = this.channels[chIndex];
        ch.note = note;
        ch.active = true;

        // Ensure channel has current patch data (sanity check)
        this.writePatchToChannel(chIndex, this.currentPatch);

        // Freq Calculation
        // FNum = (Freq * 2^20 * 144) / (Clock * 2^(Block-1))
        const freq = 440 * Math.pow(2, (note - 69) / 12);
        let block = Math.floor((note - 12) / 12); 
        if (block < 0) block = 0; 
        if (block > 7) block = 7;

        const mult = (freq * 1048576 * 144) / CLOCK_SPEED;
        let fnum = Math.round(mult / Math.pow(2, block - 1));

        // Overflow check
        while (fnum > 2047 && block < 7) {
            block++;
            fnum = Math.round(mult / Math.pow(2, block - 1));
        }
        if (fnum > 2047) fnum = 2047;

        const part = chIndex < 3 ? 0 : 1;
        const addrOffset = part === 1 ? 0x100 : 0;
        const chIdx = chIndex % 3;

        // Write F-Number
        // A4: Block (3 bits) | FNum High (3 bits)
        this.write(addrOffset + 0xA4 + chIdx, (block << 3) | ((fnum >> 8) & 0x07));
        // A0: FNum Low (8 bits)
        this.write(addrOffset + 0xA0 + chIdx, fnum & 0xFF);

        // Key On (Reg 0x28)
        // Channel: 0-2 = 0-2; 3-5 = 4-6 (Bit 2 set)
        const keyOnCh = chIndex < 3 ? chIndex : (chIndex + 1);
        // 0xF0 = All 4 slots Key On
        this.write(0x28, 0xF0 | keyOnCh);
    }

    noteOff(note: number) {
        // Find all channels playing this note
        this.channels.forEach((ch, idx) => {
            if (ch.note === note && ch.active) {
                ch.active = false;
                const keyOnCh = idx < 3 ? idx : (idx + 1);
                // 0x00 = All slots Key Off
                this.write(0x28, 0x00 | keyOnCh);
            }
        });
    }

    processAudio(e: AudioProcessingEvent) {
        const output = e.outputBuffer;
        const chanL = output.getChannelData(0);
        const chanR = output.getChannelData(1);
        
        // Get raw samples from emulator
        const samples = this.ym2612.update(output.length);
        
        // Normalize
        // Emulator returns ~14-bit signed integers (+- 8192)
        // We divide by 8192 to get +- 1.0 range, but let's be safe with headroom
        const GAIN = 1.0 / 4096.0; // Louder

        for (let i = 0; i < output.length; i++) {
            chanL[i] = samples[0][i] * GAIN;
            chanR[i] = samples[1][i] * GAIN;
        }
    }

    getAnalyser() {
        return this.analyser;
    }
}
