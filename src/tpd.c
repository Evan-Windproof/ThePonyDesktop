/* SPDX-License-Identifier: GPL-3.0-or-later */
/* HoofTTY native Ring 3 application: all mutable state lives on its user stack. */
#include <stdint.h>
#include "abi.h"
#include "tpd_version.h"
static void rect(int x,int y,int w,int h,unsigned color){
    call(5,(long)((uint64_t)(unsigned)x|((uint64_t)(unsigned)y<<16)|
        ((uint64_t)(unsigned)w<<32)|((uint64_t)(unsigned)h<<48)),color);
}
static void label(int x,int y,const char *s,unsigned color){
    for(;*s;s++,x+=12)call(8,x|((long)y<<16),((long)color<<8)|(unsigned char)*s);
}
static void text(int x,int y,const char *s){label(x,y,s,0xffffff);}
static int clamp(int n,int max){return n<0?0:n>max?max:n;}
__attribute__((noreturn)) void _start(void){
    long mode=call(4,0,0);
    if(mode<0){write_text("TPD: display or PS/2 mouse unavailable\n");finish();}
    if(call(9,0,0)<0){write_text("TPD: buffered mode requires at most 1024x768\n");call(7,0,0);finish();}
    int w=mode&65535,h=(mode>>16)&65535,x=60,y=60,mx=w/2,my=h/2;
    int visible=1,drag=0,ox=0,oy=0,old=0,dirty=1;
    write_text("TPD v" TPD_VERSION ": Ring 3 desktop ready\n");
    for(;;){
        if(dirty){
            rect(0,0,w,h,0x244754);
            rect(0,h-32,w,32,0x172932);
            text(8,h-24,"TPD " TPD_VERSION);text(w-96,h-24,"EXIT [Q]");
            if(visible){
                rect(x,y,300,170,0x101820);rect(x+2,y+2,296,166,0xdee4e8);
                rect(x+2,y+2,296,26,0x345c80);text(x+10,y+8,"DEMO WINDOW");
                rect(x+272,y+4,22,22,0x9f3941);text(x+278,y+8,"X");
                /* Body uses the same simple glyph service, no host fonts. */
                label(x+12,y+54,"THE PONY DESKTOP",0x172932);label(x+12,y+80,"DRAG THE TITLE BAR",0x172932);
            }
            for(int i=0;i<12;i++)rect(mx,my+i,1+i/2,1,0xffffff);
            call(10,0,0);dirty=0;
        }
        long e=call(6,0,0);if(e<0)break;
        int nx=e&65535,ny=(e>>16)&65535,down=(e>>32)&1,key=(e>>40)&255;
        if(key=='q'||key=='Q')break;
        if(down&&!old){
            if(ny>=h-32&&nx>=w-100)break;
            if(visible&&nx>=x&&nx<x+300&&ny>=y&&ny<y+28){
                if(nx>=x+272){visible=0;dirty=1;write_text("TPD: window closed\n");}
                else {drag=1;ox=nx-x;oy=ny-y;write_text("TPD: drag begin\n");}
            }
        }
        if(!down&&drag){drag=0;write_text("TPD: drag end\n");}
        if(drag){x=clamp(nx-ox,w-300);y=clamp(ny-oy,h-202);dirty=1;}
        if(nx!=mx||ny!=my){mx=nx;my=ny;dirty=1;}
        old=down;
    }
    call(7,0,0);write_text("TPD: returned to Shell\n");finish();
}
