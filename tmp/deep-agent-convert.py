import sys, os, math, json
sys.path.insert(0, '/tmp/deep-agent-video-decoder')
import av
from PIL import Image, ImageDraw

src='/Volumes/Storage/LangGraph_AgentChat_ui_Opencode_CLI/logs/scroll observation video.mov'
out='/tmp/deep-agent-video-stills'
os.makedirs(out, exist_ok=True)
for n in os.listdir(out):
    p=os.path.join(out,n)
    if os.path.isfile(p): os.unlink(p)

container=av.open(src)
stream=next(s for s in container.streams if s.type=='video')
next_sample=0.0
sample_interval=1.0
saved=[]
source_frames=0
width=height=None
last_time=-1.0
for frame in container.decode(stream):
    source_frames += 1
    width, height = frame.width, frame.height
    t=frame.time
    if t is None:
        if frame.pts is None or stream.time_base is None:
            continue
        t=float(frame.pts * stream.time_base)
    t=float(t)
    last_time=max(last_time,t)
    if t + 1e-9 >= next_sample:
        stamp=f'{t:010.3f}'.replace('.','_')
        path=os.path.join(out, f'frame_{len(saved):06d}_t{stamp}s.jpg')
        frame.to_image().save(path, format='JPEG', quality=88, optimize=True)
        saved.append((path,t))
        while next_sample <= t + 1e-9:
            next_sample += sample_interval
container.close()

contact=None
chosen=[]
if saved:
    max_tiles=600
    chosen=saved if len(saved)<=max_tiles else [saved[round(i*(len(saved)-1)/(max_tiles-1))] for i in range(max_tiles)]
    cols=5; tile_w=320; tile_h=200; label_h=24
    rows=math.ceil(len(chosen)/cols)
    sheet=Image.new('RGB',(cols*tile_w, rows*(tile_h+label_h)), 'white')
    draw=ImageDraw.Draw(sheet)
    for i,(path,t) in enumerate(chosen):
        im=Image.open(path).convert('RGB')
        im.thumbnail((tile_w-8,tile_h-8), Image.Resampling.LANCZOS)
        x=(i%cols)*tile_w+(tile_w-im.width)//2
        y=(i//cols)*(tile_h+label_h)+(tile_h-im.height)//2
        sheet.paste(im,(x,y))
        draw.text(((i%cols)*tile_w+6,(i//cols)*(tile_h+label_h)+tile_h+3),f'{t:.3f}s',fill='black')
    contact=os.path.join(out,'contact_sheet.jpg')
    sheet.save(contact,format='JPEG',quality=85,optimize=True)

summary={'source':src,'destination':out,'decoder':'PyAV 18.0.0 (bundled FFmpeg libraries), sequential decode','sampling_interval_seconds':sample_interval,'frame_count':len(saved),'source_decoded_frames':source_frames,'duration_seconds_approx':(last_time if last_time>=0 else None),'dimensions':[width,height],'contact_sheet':contact,'contact_sheet_tiles':len(chosen),'files':[os.path.basename(p) for p,_ in saved]}
with open(os.path.join(out,'conversion_summary.txt'),'w') as f:
    for k,v in summary.items(): f.write(f'{k}: {v}\n')
print(json.dumps({k:v for k,v in summary.items() if k!='files'}, indent=2))
