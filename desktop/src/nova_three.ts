import * as THREE from 'three'

export type NovaThreeAvatar={setMotion(enabled:boolean):void;dispose():void}
type Position=readonly[number,number,number]

/** Adapted from the earlier Nova hologram: local geometry, no model/texture downloads.
 * It remains decorative, like Nova 2D; it does not imply an execution state. */
export function createNovaThreeAvatar(host:HTMLElement,motionEnabled:boolean,onUnavailable:()=>void):NovaThreeAvatar{
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'})
  renderer.setClearColor(0x000000,0)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5))
  renderer.outputColorSpace=THREE.SRGBColorSpace
  renderer.domElement.setAttribute('aria-hidden','true')
  host.append(renderer.domElement)
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(35,1,.1,20),whole=new THREE.Group()
  camera.position.set(0,0,6.15);scene.add(whole)
  scene.add(new THREE.AmbientLight(0xffffff,1.65))
  const keyLight=new THREE.DirectionalLight(0xffffff,2.65);keyLight.position.set(-2,3,5);scene.add(keyLight)
  const fillLight=new THREE.DirectionalLight(0xffffff,.7);fillLight.position.set(3,-1,2);scene.add(fillLight)
  const geometries:THREE.BufferGeometry[]=[],materials:THREE.Material[]=[]
  const geometry=<T extends THREE.BufferGeometry>(item:T):T=>{geometries.push(item);return item}
  const material=<T extends THREE.Material>(item:T):T=>{materials.push(item);return item}
  const sphere=(radius:number,latitude:number,longitude:number):Position=>[
    radius*Math.cos(latitude)*Math.cos(longitude),radius*Math.sin(latitude),radius*Math.cos(latitude)*Math.sin(longitude)]
  const segment=(positions:number[],a:Position,b:Position)=>positions.push(...a,...b)
  const lines=(positions:number[])=>{const value=geometry(new THREE.BufferGeometry());value.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));return value}
  // Broken traces leave the center readable and give the shells a holographic depth.
  function shell(radius:number,parallels:number,meridians:number,seed:number){
    const traces:number[]=[],lights:number[]=[]
    for(let i=0;i<parallels;i++){
      const latitude=-1.28+i/(parallels-1)*2.56
      for(let step=0;step<96;step++){
        if((step+i*7+seed)%17<5)continue
        segment(traces,sphere(radius,latitude,step/96*Math.PI*2),sphere(radius,latitude,(step+1)/96*Math.PI*2))
      }
    }
    for(let i=0;i<meridians;i++){
      const longitude=i/meridians*Math.PI*2+seed*.13
      for(let step=0;step<64;step++){
        if((step+i*3+seed)%19<7)continue
        segment(traces,sphere(radius,-1.34+step/64*2.68,longitude),sphere(radius,-1.34+(step+1)/64*2.68,longitude))
      }
    }
    for(let i=0;i<38;i++)lights.push(...sphere(radius+.006,Math.asin(-.88+((i*.618034+seed*.13)%1)*1.76),i*2.399963+seed))
    const traceMaterial=material(new THREE.LineBasicMaterial({color:0xffffff,transparent:true,opacity:.48,depthWrite:false}))
    const pointMaterial=material(new THREE.PointsMaterial({color:0xffffff,size:.027,transparent:true,opacity:.8,depthWrite:false}))
    const group=new THREE.Group();group.add(new THREE.LineSegments(lines(traces),traceMaterial));group.add(new THREE.Points(lines(lights),pointMaterial));whole.add(group)
    return{group,traceMaterial,pointMaterial}
  }
  const inner=shell(.87,7,9,2),outer=shell(1.24,11,15,7)
  inner.group.rotation.set(.24,0,.28);outer.group.rotation.set(-.17,0,-.3)
  // Sparse ambient dust: one draw, fixed buffers, no textures or extra animation loop.
  const dustLayout=[[-.88,-.65],[-.66,.24],[-.94,.62],[-.42,.88],[-.28,-.84],[.05,.9],[.29,.84],
    [.58,.55],[.89,.78],[.78,.13],[.95,-.45],[.51,-.85],[-.72,-.16],[.87,-.81]] as const
  const dustPhases=dustLayout.map((_,i)=>(i*.618034%1)*Math.PI*2)
  const dustGeometry=geometry(new THREE.BufferGeometry())
  dustGeometry.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(dustLayout.length*3),3))
  dustGeometry.setAttribute('phase',new THREE.Float32BufferAttribute(dustPhases,1))
  const dustMaterial=material(new THREE.ShaderMaterial({
    transparent:true,depthWrite:false,toneMapped:false,
    uniforms:{uColor:{value:new THREE.Color()},uTime:{value:0},uPixelRatio:{value:renderer.getPixelRatio()},uOpacity:{value:.32}},
    vertexShader:`
      attribute float phase;
      uniform float uTime;
      uniform float uPixelRatio;
      varying float vGlow;
      void main(){
        vec3 drift=vec3(sin(uTime*.13+phase)*.035,cos(uTime*.1+phase)*.045,0.);
        gl_Position=projectionMatrix*modelViewMatrix*vec4(position+drift,1.);
        gl_PointSize=(1.6+.8*fract(phase))*uPixelRatio;
        vGlow=.75+.2*sin(uTime*.18+phase);
      }`,
    fragmentShader:`
      uniform vec3 uColor;
      uniform float uOpacity;
      varying float vGlow;
      void main(){
        float glow=1.-smoothstep(.08,.5,length(gl_PointCoord-vec2(.5)));
        gl_FragColor=vec4(uColor,uOpacity*vGlow*glow);
        #include <colorspace_fragment>
      }`,
  }))
  scene.add(new THREE.Points(dustGeometry,dustMaterial))
  const haloMaterial=material(new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.025,depthWrite:false,side:THREE.BackSide}))
  whole.add(new THREE.Mesh(geometry(new THREE.SphereGeometry(1.26,24,16)),haloMaterial))
  const coreMaterial=material(new THREE.MeshStandardMaterial({color:0xffffff,emissive:0xffffff,emissiveIntensity:.18,metalness:.35,roughness:.27}))
  const core=new THREE.Mesh(geometry(new THREE.TorusGeometry(.33,.105,20,64)),coreMaterial)
  core.rotation.set(-.21,.19,0);whole.add(core)
  const glowMaterial=material(new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.1,depthWrite:false}))
  const glow=new THREE.Mesh(geometry(new THREE.TorusGeometry(.33,.16,12,48)),glowMaterial);glow.position.z=-.065;glow.rotation.copy(core.rotation);whole.add(glow)
  const orbitMaterial=material(new THREE.LineBasicMaterial({color:0xffffff,transparent:true,opacity:.6,depthWrite:false}))
  const nodeMaterial=material(new THREE.MeshStandardMaterial({color:0xffffff,emissive:0xffffff,emissiveIntensity:.55,roughness:.24}))
  const nodeGeometry=geometry(new THREE.SphereGeometry(.04,10,8))
  const orbits=[{radius:1.34,x:.72,y:.3},{radius:1.3,x:-.58,y:-.24}].map(({radius,x,y},i)=>{
    const group=new THREE.Group(),arc:number[]=[];group.rotation.set(x,y,i*.68)
    for(let step=0;step<128;step++){
      if((step+i*11)%31<8)continue
      const start=step/128*Math.PI*2,end=(step+1)/128*Math.PI*2
      segment(arc,[radius*Math.cos(start),radius*Math.sin(start),0],[radius*Math.cos(end),radius*Math.sin(end),0])
    }
    group.add(new THREE.LineSegments(lines(arc),orbitMaterial))
    const node=new THREE.Mesh(nodeGeometry,nodeMaterial);node.position.set(radius,0,0);group.add(node);whole.add(group);return group
  })
  let disposed=false,intersecting=true,wantsMotion=motionEnabled,lastFrame=0,elapsed=0,frames=0
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)')
  function draw(){if(disposed)return;renderer.render(scene,camera);host.dataset.renderFrames=String(++frames)}
  function frame(time:number){
    if(disposed||time-lastFrame<33)return
    if(!wantsMotion||reduced.matches||document.hidden||!intersecting||host.closest('[inert]')){syncMotion();return}
    const delta=lastFrame?Math.min(.08,(time-lastFrame)/1000):0;lastFrame=time;elapsed+=delta
    dustMaterial.uniforms.uTime.value=elapsed
    orbits[0].rotation.z+=delta*.31;orbits[1].rotation.z-=delta*.22
    inner.group.rotation.y+=delta*.075;outer.group.rotation.y-=delta*.04;outer.group.rotation.x+=delta*.007
    whole.rotation.y=Math.sin(elapsed*.3)*.12;whole.rotation.x=Math.sin(elapsed*.23)*.065
    const pulse=1+Math.sin(elapsed*1.7)*.022;core.scale.setScalar(pulse);glow.scale.setScalar(pulse*1.04)
    draw()
  }
  function syncMotion(){
    if(disposed)return
    const moving=wantsMotion&&!reduced.matches&&!document.hidden&&intersecting&&host.clientWidth>0&&host.clientHeight>0&&!host.closest('[inert]')
    lastFrame=0;host.dataset.animating=String(moving);renderer.setAnimationLoop(moving?frame:null)
    if(!moving)draw()
  }
  function resize(){
    if(disposed)return
    const width=host.clientWidth,height=host.clientHeight
    if(width&&height){
      renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix()
      const positions=dustGeometry.getAttribute('position')
      dustLayout.forEach(([nx,ny],i)=>{
        const depth=.6+(i%3)*.16,halfHeight=Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*(camera.position.z+depth)
        let x=nx*halfHeight*camera.aspect,y=ny*halfHeight
        // Keep ambient specks outside the original sphere and its existing particles.
        const distance=Math.hypot(x,y)
        if(distance<1.55){x*=1.55/distance;y*=1.55/distance}
        positions.setXYZ(i,x,y,-depth)
      })
      positions.needsUpdate=true;dustGeometry.computeBoundingSphere();draw()
    }
    syncMotion()
  }
  function colors(){
    if(disposed)return
    const style=getComputedStyle(host),accent=new THREE.Color(style.color),glint=accent.clone().lerp(new THREE.Color(0xffffff),.2)
    coreMaterial.color.copy(accent);coreMaterial.emissive.copy(accent);glowMaterial.color.copy(accent)
    inner.traceMaterial.color.copy(glint);outer.traceMaterial.color.copy(accent)
    inner.pointMaterial.color.copy(glint);outer.pointMaterial.color.copy(glint)
    orbitMaterial.color.copy(accent);nodeMaterial.color.copy(accent);nodeMaterial.emissive.copy(accent);haloMaterial.color.copy(accent)
    dustMaterial.uniforms.uColor.value.copy(accent)
    const light=document.documentElement.dataset.novaScheme==='light'
    dustMaterial.uniforms.uOpacity.value=light ? .28 : .32
    glowMaterial.opacity=light ? .035 : .1;inner.traceMaterial.opacity=light ? .55 : .52;outer.traceMaterial.opacity=light ? .44 : .4
    draw()
  }
  const resized=new ResizeObserver(resize),visible=new IntersectionObserver(entries=>{intersecting=entries[0]?.isIntersecting??false;syncMotion()})
  const themed=new MutationObserver(()=>{colors();syncMotion()})
  const blocked=new MutationObserver(syncMotion)
  function contextLost(event:Event){event.preventDefault();if(!disposed){renderer.setAnimationLoop(null);onUnavailable()}}
  renderer.domElement.addEventListener('webglcontextlost',contextLost)
  reduced.addEventListener('change',syncMotion);document.addEventListener('visibilitychange',syncMotion)
  resized.observe(host);visible.observe(host)
  themed.observe(document.documentElement,{attributes:true,attributeFilter:['style','data-nova-theme','data-nova-scheme']})
  const root=document.getElementById('root');if(root)blocked.observe(root,{attributes:true,attributeFilter:['inert']})
  colors();resize()
  return{
    setMotion(enabled){wantsMotion=enabled;syncMotion()},
    dispose(){
      if(disposed)return;disposed=true;renderer.setAnimationLoop(null)
      resized.disconnect();visible.disconnect();themed.disconnect();blocked.disconnect()
      reduced.removeEventListener('change',syncMotion);document.removeEventListener('visibilitychange',syncMotion)
      renderer.domElement.removeEventListener('webglcontextlost',contextLost)
      geometries.forEach(item=>item.dispose());materials.forEach(item=>item.dispose());renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove()
      delete host.dataset.renderFrames;delete host.dataset.animating
    },
  }
}
