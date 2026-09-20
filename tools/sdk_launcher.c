/* Start the selected engine with the SDK's Citadel content project. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef int (*Source2MainFn)(void *, void *, const char *, int, const char *, const char *);

int WINAPI WinMain(HINSTANCE instance, HINSTANCE previous, LPSTR command_line, int show)
{
    /* Resolve dependencies beside this executable, never from the caller's cwd. */
    char directory[32768];
    DWORD length = GetModuleFileNameA(NULL, directory, sizeof(directory));
    if (length == 0 || length >= sizeof(directory)) {
        fprintf(stderr, "sdk_launcher: cannot resolve executable directory\n");
        return 1;
    }
    char *separator = strrchr(directory, '\\');
    if (separator == NULL) {
        fprintf(stderr, "sdk_launcher: executable has no parent directory\n");
        return 1;
    }
    *separator = '\0';
    if (!SetCurrentDirectoryA(directory) || !SetDllDirectoryA(directory)) {
        fprintf(stderr, "sdk_launcher: cannot select SDK binary directory (%lu)\n", GetLastError());
        return 1;
    }

    /* The engine's own entry point controls tools startup and process lifetime. */
    SetEnvironmentVariableA("Source2Launcher", "1");
    HMODULE engine = LoadLibraryA("engine2.dll");
    if (engine == NULL) {
        fprintf(stderr, "sdk_launcher: cannot load engine2.dll (%lu)\n", GetLastError());
        return 1;
    }
    Source2MainFn start = (Source2MainFn)GetProcAddress(engine, "Source2Main");
    if (start == NULL) {
        fprintf(stderr, "sdk_launcher: engine2.dll has no Source2Main export\n");
        FreeLibrary(engine);
        return 1;
    }
    return start(instance, previous, command_line, show, directory, "citadel");
}
