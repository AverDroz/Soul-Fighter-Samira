#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>

static HMODULE module;
static LONG started;

/* Only create a worker in ModInit. Never start Python or wait under DllMain's
   loader lock, and never hook the game's rendering/input functions. */
static DWORD WINAPI launch(void *unused) {
    wchar_t ini[32768], root[32768], game[32768], python[32768];
    wchar_t command[32768];
    GetModuleFileNameW(module, ini, 32768);
    wchar_t *slash = wcsrchr(ini, L'\\');
    if (!slash) return 0;
    wcscpy(slash + 1, L"samira-companion.ini");
    if (GetPrivateProfileIntW(L"Samira", L"Protocol", 0, ini) != 1) return 0;
    GetPrivateProfileStringW(L"Samira", L"Runtime", L"", root, 32768, ini);
    GetPrivateProfileStringW(L"Samira", L"Game", L"", game, 32768, ini);
    if (!*root || !*game || wcschr(root, L'"') || wcschr(game, L'"')) return 0;
    if (swprintf(python, 32768, L"%ls\\python\\pythonw.exe", root) < 0) return 0;
    if (swprintf(command, 32768,
        L"\"%ls\" -I -B \"%ls\\companion.py\" --game-pid %lu --game-dir \"%ls\"",
        python, root, GetCurrentProcessId(), game) < 0) return 0;
    STARTUPINFOW si = {0}; PROCESS_INFORMATION pi = {0}; si.cb = sizeof(si);
    if (CreateProcessW(python, command, NULL, NULL, FALSE, CREATE_NO_WINDOW,
                       NULL, root, &si, &pi)) {
        CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    }
    return 0;
}

__declspec(dllexport) int ModInit(void) {
    if (InterlockedCompareExchange(&started, 1, 0) == 0) {
        HANDLE thread = CreateThread(NULL, 0, launch, NULL, 0, NULL);
        if (thread) CloseHandle(thread);
    }
    /* Missing/corrupt companion must not stop REPENTOGON from starting. */
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {module = instance; DisableThreadLibraryCalls(instance);}
    return TRUE;
}
