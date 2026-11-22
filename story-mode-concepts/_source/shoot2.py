import os
from playwright.sync_api import sync_playwright
from PIL import Image
OUT='/mnt/user-data/outputs/story-mode-concepts'
ORDER=[('perk','03-perk-card-choice'),('catalog','03b-perk-catalog'),('c1','intro-1-the-breach'),('c2','intro-2-the-checkpoint'),('c3','intro-3-the-chase'),('c4','intro-4-lockdown'),('c5','intro-5-the-mission'),('c6','intro-6-title'),
 ('qa','boss-1a-queen-approach'),('qr','boss-1b-queen-reveal'),('za','boss-2a-zero-approach'),('zr','boss-2b-zero-reveal')]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--allow-file-access-from-files'])
    pg=b.new_page(viewport={'width':1280,'height':720},device_scale_factor=1.5);errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('file:///home/claude/story/story.html');pg.evaluate("()=>window.ready")
    for k,n in ORDER:
        pg.evaluate("n=>window.render(n)",k);pg.locator('#c').screenshot(path=f'{OUT}/{n}.png')
    print('errs',errs);b.close()
# opening storyboard sheet
fs=[f'{OUT}/intro-{i}.png' for i in ['1-the-breach','2-the-checkpoint','3-the-chase','4-lockdown','5-the-mission','6-title']]
sh=Image.new('RGB',(1920,840),'#020806')
for i,f in enumerate(fs):sh.paste(Image.open(f).convert('RGB').resize((620,349)),(15+(i%3)*635,90+(i//3)*370))
from PIL import ImageDraw,ImageFont
d=ImageDraw.Draw(sh)
try:F=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',40)
except:F=None
d.text((960,45),'OPENING CINEMATIC  -  STORYBOARD',fill='#5dff3a',font=F,anchor='mm')
sh.save(f'{OUT}/intro-0-storyboard.png')
