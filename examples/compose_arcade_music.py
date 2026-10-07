"""Original eight-second arcade backing loop; no sampled or licensed assets."""
import math, wave, struct, random
from pathlib import Path
rate=48000; duration=8; n=rate*duration
mix=[0.0]*n
rng=random.Random(7)
def note(midi): return 440*2**((midi-69)/12)
def add(start,length,midi,gain,kind='pulse'):
    offset=int(start*rate); count=int(length*rate); f=note(midi)
    for j in range(count):
        if offset+j>=n: break
        t=j/rate; phase=2*math.pi*f*t
        if kind=='bass': sound=math.sin(phase)+0.2*math.sin(2*phase)
        else: sound=math.sin(phase)+0.3*math.sin(3*phase)+0.12*math.sin(5*phase)
        env=min(1,t/.008)*min(1,(length-t)/.035)*math.exp(-t/(length*1.1))
        mix[offset+j]+=gain*env*sound
# A minor, F, C, G — four two-second bars at 120 BPM.
chords=[(57,60,64,69),(53,57,60,65),(55,60,64,67),(55,59,62,67)]
pattern=[0,2,1,3,2,1,2,3]
for bar,chord in enumerate(chords):
    for step,index in enumerate(pattern):
        add(bar*2+step*.25,.20,chord[index]+12,.065)
    for beat in range(4):
        add(bar*2+beat*.5,.40,chord[0]-12,.085,'bass')
# Light synthesized kick and noise hat, beneath the gameplay effects.
for beat in range(16):
    start=int(beat*.5*rate)
    for j in range(int(.12*rate)):
        t=j/rate; phase=2*math.pi*(55*t+45*.025*(1-math.exp(-t/.025)))
        mix[start+j]+=.065*math.sin(phase)*math.exp(-t/.035)
for eighth in range(32):
    start=int(eighth*.25*rate)
    for j in range(int(.025*rate)):
        mix[start+j]+=.012*rng.uniform(-1,1)*math.exp(-j/rate/.008)
# Short edge fades and 10 dB dips at the three expected impacts.
for i in range(n):
    t=i/rate; envelope=min(1,t/.10,(duration-t)/.25)
    for hit in (1.8,4.0,6.2):
        if hit-.08 <= t < hit: envelope*=1-.68*(t-(hit-.08))/.08
        elif hit <= t < hit+.18: envelope*=.32
        elif hit+.18 <= t < hit+.48: envelope*=.32+.68*(t-hit-.18)/.30
    mix[i]*=max(0,envelope)
p=Path(__file__).parent/'arcade-backing.wav'
with wave.open(str(p),'wb') as w:
    w.setparams((1,2,rate,n,'NONE','not compressed'))
    w.writeframes(b''.join(struct.pack('<h',round(max(-1,min(1,x))*32767)) for x in mix))
print(p)
