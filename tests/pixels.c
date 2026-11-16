/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <limine.h>
#include <kernseed/console.h>
#include <kernseed/pixels.h>
static uint32_t storage[3+40*32+3];
int main(void){
    struct limine_framebuffer fb={.address=storage+3,.width=32,.height=32,.pitch=40*4,
        .bpp=32,.memory_model=1,.red_mask_size=8,.green_mask_size=8,.blue_mask_size=8,
        .red_mask_shift=0,.green_mask_shift=8,.blue_mask_shift=16};
    for(unsigned i=0;i<sizeof(storage)/sizeof(*storage);i++)storage[i]=0xdeadbeef;
    assert(framebuffer_init(&fb));assert(pixels_size()==(32|(32UL<<16)));
    pixels_rect(31,31,65535,65535,0x123456);
    assert(storage[3+31*40+31]==0x563412);
    pixels_rect(65535,65535,65535,65535,0xffffff);
    pixels_rect(0,0,0,65535,0xffffff);
    pixels_glyph(30,30,'W',0xaabbcc);pixels_glyph(65535,65535,'A',0xffffff);
    pixels_glyph(0,0,255,0xffffff);
    for(unsigned y=0;y<32;y++)for(unsigned x=32;x<40;x++)assert(storage[3+y*40+x]==0xdeadbeef);
    for(unsigned i=0;i<3;i++){assert(storage[i]==0xdeadbeef);assert(storage[3+40*32+i]==0xdeadbeef);}
    assert(pixels_begin()==0);assert(pixels_begin()==-16);
    pixels_rect(0,0,2,2,0x123456);assert(storage[3]==0);
    assert(pixels_present()==0);assert(storage[3]==0x563412);
    assert(pixels_present()==0);pixels_end();assert(pixels_present()==-1);
    framebuffer_clear();
    pixels_pause(true);framebuffer_putc('X');assert(storage[3]==0);
    pixels_pause(false);framebuffer_putc('X');assert(storage[3]!=0);
    puts("PASS graphics: clipping, padding canaries, RGB masks, invalid glyph, terminal suspension");
}
