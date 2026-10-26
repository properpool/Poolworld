"""Pool World v10.0 regression: reuse decoded HTMLAudioElement voices after playback.
Real Chromium fixtures use deterministic fake media nodes; they do not prove
Samsung audio latency, audible quality or hardware acceptance.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,sys

ROOT=Path(__file__).resolve().parent.parent
HTML=(ROOT/'POOL_WORLD_6.0_STAGING_MATCH.html').read_text()
checks=[]
def check(name,passed,detail):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed: print('FAIL',name,json.dumps(detail),flush=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,
        executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
        args=['--no-sandbox'])
    for width,height in [(390,844),(844,390),(768,1024),(1366,768)]:
        label=f'{width}x{height}'
        page=browser.new_page(viewport={'width':width,'height':height},
            is_mobile=width<1000,has_touch=width<1000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate('window.requestAnimationFrame=()=>0')
        page.set_content(HTML,wait_until='load')
        result=page.evaluate("""() => {
            const names=['ball','cue','pocket','rail'];
            const original=Object.fromEntries(names.map(k=>[k,soundBases[k]]));
            const stats={};
            const savedSoundOn=soundOn;
            try {
                soundOn=true;
                for(const k of names){
                    stats[k]={created:0,voices:[],plays:0,rewinds:0};
                    soundBases[k]={
                        cloneNode(){
                            stats[k].created++;
                            const voice={paused:true,ended:false,_time:0,volume:0,
                                playbackRate:1,plays:0,
                                get currentTime(){return this._time},
                                set currentTime(v){if(v===0&&this._time>0)stats[k].rewinds++;this._time=v},
                                play(){this.paused=false;this.ended=false;
                                    this.plays++;stats[k].plays++;
                                    return Promise.resolve()}
                            };
                            stats[k].voices.push(voice);
                            return voice;
                        }
                    };
                }
                const emit=(k,level=.8)=>{
                    lastSound[k==='cushion'?'rail':k]=-100000;
                    sound(k,level);
                };
                // Completed impacts should recycle a single media element.
                for(let i=0;i<32;i++){
                    emit('rail',.8);
                    const voice=stats.rail.voices.at(-1);
                    voice.paused=true;voice.ended=true;voice.currentTime=2.1;
                }
                const sequential={created:stats.rail.created,plays:stats.rail.plays,
                    rewinds:stats.rail.rewinds,volumes:stats.rail.voices.map(v=>v.volume),
                    rates:stats.rail.voices.map(v=>v.playbackRate)};
                // Four simultaneously playing impacts require four distinct voices.
                for(let i=0;i<4;i++)emit('ball',.6);
                const concurrent={created:stats.ball.created,
                    distinct:new Set(stats.ball.voices).size,plays:stats.ball.plays};
                stats.ball.voices[0].paused=true;
                stats.ball.voices[0].ended=true;
                stats.ball.voices[0].currentTime=1.2;
                emit('ball',.7);
                const recovered={created:stats.ball.created,
                    plays:stats.ball.plays,firstPlays:stats.ball.voices[0].plays,
                    rewinds:stats.ball.rewinds};
                // Cushion alias must share rail voice pool, not create a fifth type.
                emit('cushion',.4);
                const alias={created:stats.rail.created,plays:stats.rail.plays,
                    volume:stats.rail.voices[0]?.volume};
                emit('cue',.9);emit('pocket',.9);
                const isolated={cue:stats.cue.created,pocket:stats.pocket.created,
                    rail:stats.rail.created,ball:stats.ball.created};
                const before=Object.values(stats).reduce((s,x)=>s+x.plays,0);
                soundOn=false;emit('ball',1);soundOn=true;
                const afterMute=Object.values(stats).reduce((s,x)=>s+x.plays,0);
                lastSound.ball=performance.now();sound('ball',1);
                const afterThrottle=Object.values(stats).reduce((s,x)=>s+x.plays,0);
                return {sequential,concurrent,recovered,alias,isolated,
                    before,afterMute,afterThrottle,
                    recordedIntact:names.every(k=>typeof RECORDED_SOUNDS[k]==='string' &&
                        RECORDED_SOUNDS[k].startsWith('data:audio/'))};
            }finally{
                for(const k of names)soundBases[k]=original[k];
                soundOn=savedSoundOn;
            }
        }""")
        s=result['sequential'];c=result['concurrent'];r=result['recovered']
        a=result['alias'];i=result['isolated']
        check(label+' sequential 32 impacts played',s['plays']==32,s)
        check(label+' completed impacts reuse one audio clone',s['created']==1,s)
        check(label+' replay rewinds previously completed sound',s['rewinds']>=30,s)
        check(label+' sound volume stays calibrated',all(.07<=v<=.92 for v in s['volumes']),s)
        check(label+' sound pitch stays within original variation',
            all(.96<=v<=1.04 for v in s['rates']),s)
        check(label+' four overlapping impacts play separately',
            c['plays']==4 and c['distinct']==4,c)
        check(label+' overlapping impacts allocate only four voices',c['created']==4,c)
        check(label+' completed concurrent voice reused without new clone',
            r['created']==4 and r['plays']==5 and r['firstPlays']==2,r)
        check(label+' concurrent voice restarts from beginning',r['rewinds']>=1,r)
        check(label+' cushion alias reuses rail voice',a['created']==1 and a['plays']==33,a)
        check(label+' four sound types retain independent pools',
            i['cue']==1 and i['pocket']==1 and i['rail']==1 and i['ball']==4,i)
        check(label+' mute blocks playback',result['before']==result['afterMute'],result)
        check(label+' sound throttle still blocks duplicate',result['afterMute']==result['afterThrottle'],result)
        check(label+' four recorded sound data URIs remain present',result['recordedIntact'],result)
        check(label+' no browser exceptions',not errors,errors)
        print('AUDIO_VOICE_DIAGNOSTIC',label,json.dumps(result),flush=True)
        page.close()
    browser.close()

passed=sum(c['passed'] for c in checks)
(ROOT/'POOL_WORLD_6.0_AUDIO_VOICE_RESULTS.json').write_text(json.dumps({
    'passed':passed,'total':len(checks),'checks':checks,
    'limitations':'Deterministic fake media nodes in Chromium, not physical Samsung audio.'},indent=2))
print('SUMMARY',passed,'/',len(checks),flush=True)
if passed!=len(checks):sys.exit(1)
