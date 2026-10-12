using System.Text;
using System.Text.Json;

namespace NovaBrowserHost;

// Private extraction representation. Never returned as a public observation.
internal readonly record struct PageDerivedTextLeaf(string Kind,string Text);
internal static class PageDerivedTextLeaves
{
    internal const int MaxLeaves=1024, MaxLeafChars=32768, MaxRawChars=65536, MaxPayloadUtf8=262144;
    internal static List<PageDerivedTextLeaf> Read(JsonElement leaves,int maxRawChars=MaxRawChars)
    {
        Protocol.Need(leaves.ValueKind==JsonValueKind.Array,"OBSERVATION_LIMIT");
        Protocol.Need(Encoding.UTF8.GetByteCount(leaves.GetRawText())<=MaxPayloadUtf8,"OBSERVATION_LIMIT");
        var result=new List<PageDerivedTextLeaf>();int total=0;
        foreach(var leaf in leaves.EnumerateArray())
        {
            Protocol.Closed(leaf,"kind","text");
            string kind=Protocol.Text(leaf.GetProperty("kind")),text=Protocol.Text(leaf.GetProperty("text"));
            Protocol.Need(kind is "TEXT" or "LABEL"&&text.Length<=MaxLeafChars&&result.Count<MaxLeaves,"OBSERVATION_LIMIT");
            total=checked(total+text.Length);Protocol.Need(total<=maxRawChars,"OBSERVATION_LIMIT");
            result.Add(new(kind,text));
        }
        return result;
    }
    internal static string SafeSummary(IEnumerable<PageDerivedTextLeaf> leaves,Func<string,string> redact,string separator=" ")
    {
        var safe=new List<string>();int total=0;
        foreach(var leaf in leaves)
        {
            Protocol.Need(safe.Count<MaxLeaves&&leaf.Text.Length<=MaxLeafChars,"OBSERVATION_LIMIT");
            string value=redact(leaf.Text); // ORIGINAL page leaf, before separator.
            total=checked(total+value.Length+(safe.Count==0?0:separator.Length));
            Protocol.Need(total<=MaxRawChars,"OBSERVATION_LIMIT");safe.Add(value);
        }
        return string.Join(separator,safe);
    }
}
