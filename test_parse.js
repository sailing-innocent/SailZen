// test parseNoteRefRaw logic

function parseNoteRefRaw(rawRef) {
  const optWikiFileName = /([^\]:#]*)/.source;
  const wikiFileName = /([^\]:#]+)/.source;
  const reLink = new RegExp(
    "" +
      `(?<name>${optWikiFileName})` +
      `(${
        new RegExp(
          "" +
            /#?/.source +
            `(?<anchorStart>${wikiFileName})` +
            `(:#(?<anchorEnd>${wikiFileName}))?`
        ).source
      })?`,
    "i"
  );

  // pre-parse alias if it exists
  let alias;
  let ref = rawRef;
  const parts = ref.split("|");
  const aliasPartFirst = parts[0];
  const aliasPartSecond = parts[1];
  
  if (aliasPartSecond === undefined) {
    ref = aliasPartFirst;
  } else {
    alias = aliasPartFirst;
    ref = aliasPartSecond;
  }

  console.log('after alias split - alias:', alias, ', ref:', ref);

  const groups = reLink.exec(ref) && reLink.exec(ref).groups;
  console.log('reLink groups:', JSON.stringify(groups, null, 2));
  
  let fname;
  if (groups) {
    Object.entries(groups).forEach(([k, v]) => {
      if (v === undefined) return;
      if (k === 'name') {
        const match = /^(?<name>.*?)(\.md)?$/.exec(String(v).trim());
        fname = match && match.groups && match.groups.name;
      }
    });
  }
  
  console.log('fname:', fname);
  console.log('alias:', alias);
  return { from: { fname, alias }, type: 'ref' };
}

// Test cases
console.log('=== Test 1: [[Pr|job.globalbatch.globalbatch-04-20.pr]] ===');
const result1 = parseNoteRefRaw('Pr|job.globalbatch.globalbatch-04-20.pr');
console.log('Result:', JSON.stringify(result1, null, 2));

console.log('\n=== Test 2: [[Prd|job.globalbatch.globalbatch-04-20.pr]] ===');
const result2 = parseNoteRefRaw('Prd|job.globalbatch.globalbatch-04-20.pr');
console.log('Result:', JSON.stringify(result2, null, 2));

console.log('\n=== Test 3: [[job.globalbatch.globalbatch-04-20.pr]] ===');
const result3 = parseNoteRefRaw('job.globalbatch.globalbatch-04-20.pr');
console.log('Result:', JSON.stringify(result3, null, 2));
