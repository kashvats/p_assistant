// Living Assistant v0.15 macOS Endpoint Security notification helper.
// Requires Apple-granted com.apple.developer.endpoint-security.client entitlement,
// code signing, and packaging as an appropriate system extension/app.
// This helper intentionally subscribes to NOTIFY events only; it does not authorize/block OS actions.

#include <EndpointSecurity/EndpointSecurity.h>
#include <dispatch/dispatch.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static FILE *out = NULL;

static void json_string(FILE *f, const char *s, size_t n) {
    fputc('"', f);
    for (size_t i=0; i<n; ++i) {
        unsigned char c=(unsigned char)s[i];
        if (c=='"' || c=='\\') { fputc('\\',f); fputc(c,f); }
        else if (c=='\n') fputs("\\n",f);
        else if (c=='\r') fputs("\\r",f);
        else if (c=='\t') fputs("\\t",f);
        else if (c>=0x20) fputc(c,f);
    }
    fputc('"', f);
}

static const char *event_name(es_event_type_t t) {
    switch (t) {
        case ES_EVENT_TYPE_NOTIFY_EXEC: return "exec";
        case ES_EVENT_TYPE_NOTIFY_FORK: return "fork";
        case ES_EVENT_TYPE_NOTIFY_CREATE: return "create";
        case ES_EVENT_TYPE_NOTIFY_RENAME: return "rename";
        case ES_EVENT_TYPE_NOTIFY_UNLINK: return "unlink";
        case ES_EVENT_TYPE_NOTIFY_MOUNT: return "mount";
        case ES_EVENT_TYPE_NOTIFY_SIGNAL: return "signal";
        case ES_EVENT_TYPE_NOTIFY_OPEN: return "open";
        default: return "other";
    }
}

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : getenv("LIVING_ASSISTANT_ENDPOINT_SECURITY_JSONL");
    if (!path || !*path) {
        fprintf(stderr, "usage: %s /path/to/events.jsonl\n", argv[0]);
        return 2;
    }
    out=fopen(path,"a");
    if (!out) { perror("fopen"); return 3; }
    setvbuf(out,NULL,_IOLBF,0);

    es_client_t *client=NULL;
    es_new_client_result_t r=es_new_client(&client, ^(es_client_t *c, const es_message_t *m) {
        (void)c;
        if (!m || !m->process || !m->process->executable) return;
        es_string_token_t p=m->process->executable->path;
        time_t now=time(NULL);
        fprintf(out,"{\"source\":\"macos_endpoint_security\",\"kind\":\"");
        fputs(event_name(m->event_type),out);
        fprintf(out,"\",\"time_unix\":%lld,\"event_type\":%u,\"process\":",(long long)now,(unsigned)m->event_type);
        json_string(out,p.data,p.length);
        fputs("}\n",out);
    });
    if (r != ES_NEW_CLIENT_RESULT_SUCCESS) {
        fprintf(stderr,"es_new_client failed: %d (entitlement/permissions are required)\n",(int)r);
        fclose(out); return 4;
    }

    es_event_type_t events[] = {
        ES_EVENT_TYPE_NOTIFY_EXEC, ES_EVENT_TYPE_NOTIFY_FORK,
        ES_EVENT_TYPE_NOTIFY_CREATE, ES_EVENT_TYPE_NOTIFY_RENAME,
        ES_EVENT_TYPE_NOTIFY_UNLINK, ES_EVENT_TYPE_NOTIFY_MOUNT,
        ES_EVENT_TYPE_NOTIFY_SIGNAL, ES_EVENT_TYPE_NOTIFY_OPEN
    };
    if (es_subscribe(client,events,sizeof(events)/sizeof(events[0])) != ES_RETURN_SUCCESS) {
        fprintf(stderr,"es_subscribe failed\n"); es_delete_client(client); fclose(out); return 5;
    }
    dispatch_main();
    return 0;
}
