// mac_eye.c – DYLD, IOSurface via dlsym (kein Linker-Symbol nötig)
#include "mac_eye.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <mach/mach_time.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <dlfcn.h>
#include <CoreFoundation/CoreFoundation.h>

#define kLockRO 1

static MacEyeSharedMemory *g_shm = NULL;
static int g_shm_fd = -1;
static pthread_t g_thr;
static volatile int g_run = 1;

static void *(*capture_surface)(int, unsigned int, unsigned int) = NULL;

static uint64_t nsec(void) {
    static mach_timebase_info_data_t tb = {0};
    if (tb.denom == 0) mach_timebase_info(&tb);
    return mach_absolute_time() * tb.numer / tb.denom;
}

__attribute__((constructor))
static void init(void) {
    if (!getenv("MAC_EYE_ENABLE")) return;
    // Symbol per dlsym aufloesen (kein Link-Time-Symbol)
    capture_surface = dlsym(RTLD_DEFAULT, "CGSHWCaptureWindowImageToSurface");
    if (!capture_surface) {
        fprintf(stderr, "[mac_eye] CGSHWCaptureWindowImageToSurface nicht gefunden\n");
        return;
    }
    int fd = shm_open(MAC_EYE_SHM_NAME, O_CREAT|O_RDWR, 0600);
    if (fd < 0) return;
    size_t sz = sizeof(MacEyeSharedMemory);
    ftruncate(fd, sz);
    void *ptr = mmap(NULL, sz, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
    if (ptr == MAP_FAILED) { close(fd); return; }
    g_shm_fd = fd; g_shm = ptr;
    if (g_shm->magic != 0x4D414345) {
        memset(g_shm, 0, sz);
        g_shm->magic = 0x4D414345; g_shm->version = 2;
        g_shm->target_pid = (int32_t)getpid(); g_shm->running = 1;
    }
}

__attribute__((destructor))
static void cleanup(void) {
    g_run = 0;
    if (g_thr) pthread_join(g_thr, NULL);
    if (g_shm) { g_shm->running = 0; munmap(g_shm, sizeof(MacEyeSharedMemory)); g_shm = NULL; }
    if (g_shm_fd >= 0) { close(g_shm_fd); g_shm_fd = -1; }
}

static void *capture(void *arg) {
    (void)arg;
    if (!capture_surface) return NULL;
    // CGSConnection via dlsym
    int (*get_conn)(void) = dlsym(RTLD_DEFAULT, "CGSMainConnectionID");
    int conn = get_conn ? get_conn() : 0;
    uint32_t fc = 0;
    while (g_shm->running && g_run) {
        uint64_t t0 = nsec();
        void *sf = capture_surface(conn, 0, 0);
        if (!sf) { usleep(16666); continue; }
        // IOSurface-Funktionen via dlsym
        int (*lock)(void*,unsigned int,void*) = dlsym(RTLD_DEFAULT, "IOSurfaceLock");
        int (*unlock)(void*,unsigned int,void*) = dlsym(RTLD_DEFAULT, "IOSurfaceUnlock");
        void* (*base)(void*) = dlsym(RTLD_DEFAULT, "IOSurfaceGetBaseAddress");
        size_t (*get_w)(void*) = dlsym(RTLD_DEFAULT, "IOSurfaceGetWidth");
        size_t (*get_h)(void*) = dlsym(RTLD_DEFAULT, "IOSurfaceGetHeight");
        size_t (*get_bpr)(void*) = dlsym(RTLD_DEFAULT, "IOSurfaceGetBytesPerRow");
        if (!lock || !unlock || !base || !get_w || !get_h || !get_bpr) {
            CFRelease(sf); usleep(16666); continue;
        }
        lock(sf, kLockRO, NULL);
        size_t w = get_w(sf), h = get_h(sf), bpr = get_bpr(sf);
        void *ba = base(sf);
        if (!ba) { unlock(sf, kLockRO, NULL); CFRelease(sf); usleep(16666); continue; }
        uint32_t wi = g_shm->write_index, ni = (wi + 1) % MAC_EYE_MAX_FRAMES;
        if (ni == g_shm->read_index) {
            g_shm->total_dropped++; unlock(sf, kLockRO, NULL); CFRelease(sf); usleep(1); continue;
        }
        MacEyeFrame *f = &g_shm->frames[wi];
        size_t cl = (h * bpr < sizeof(f->data)) ? h * bpr : sizeof(f->data);
        memcpy(f->data, ba, cl);
        f->timestamp_ns = t0; f->frame_index = ++fc;
        f->width = (uint32_t)w; f->height = (uint32_t)h;
        f->bytes_per_row = (uint32_t)bpr; f->pixel_format = 0x42475241;
        f->dirty = 1; g_shm->write_index = ni; g_shm->total_frames++;
        unlock(sf, kLockRO, NULL); CFRelease(sf);
        uint64_t elapsed = nsec() - t0;
        if (elapsed < 16666666) usleep((16666666 - elapsed) / 1000);
    }
    return NULL;
}

__attribute__((visibility("default")))
int mac_eye_start(void) {
    if (!g_shm || g_shm->magic != 0x4D414345) return -1;
    g_shm->running = 1; g_run = 1;
    return pthread_create(&g_thr, NULL, capture, NULL) ? -2 : 0;
}
__attribute__((visibility("default")))
int mac_eye_stop(void) { g_run = 0; if (g_shm) g_shm->running = 0; return 0; }
__attribute__((visibility("default")))
MacEyeSharedMemory *mac_eye_get(void) { return g_shm; }
