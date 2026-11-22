import os
from playwright.sync_api import sync_playwright
OUT='/mnt/user-data/outputs/story-mode-concepts';os.makedirs(OUT,exist_ok=True)
ORDER=[('flow','00-story-mode-route'),('menu','01-main-menu-and-looks'),('r1','02-room1-quarantine-wing'),('perk','03-perk-card-choice'),('trans','04-corridor-transition'),
 ('r2','05-room2-bio-lab'),('r3','06-room3-cryo-storage'),('r4','07-room4-server-core'),('r5','08-room5-reactor-escape'),('queen','09-boss-arena-hive-queen'),
 ('end','10-chapter-complete-summary'),('hive','11-chapter2-hive-tunnels'),('zero','12-boss-arena-specimen-zero')]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--allow-file-access-from-files'])
    pg=b.new_page(viewport={'width':1280,'height':720},device_scale_factor=1.5);errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('file:///home/claude/story/story.html');pg.evaluate("()=>window.ready")
    for k,n in ORDER[1:]:
        pg.evaluate("n=>window.render(n)",k);pg.locator('#c').screenshot(path=f'{OUT}/{n}.png')
    th={}
    for k,n in ORDER:
        if k in('r1','r2','r3','r4','r5','queen','hive','zero'): th[k]='file://'+OUT+'/'+n+'.png'
    pg.evaluate("a=>window.render(a[0],a[1])",['flow',th]);pg.locator('#c').screenshot(path=f'{OUT}/00-story-mode-route.png')
    print('errs',errs);b.close()
