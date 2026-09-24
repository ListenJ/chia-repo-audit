# 给组织者的邮件草稿（2026-09-24）

**发送方式**：在你自己的 Gmail（`jlinshan6@gmail.com`）里，**回到原来那条账号邮件线程**上回复，
不要新起一封；**CC** `a3-workshop-hackathon@lists.berkeley.edu`（组织者 2026-09-22 明确要求，
便于他们在列表上追这条线）。**不要用赞助账号发信**（那个账号只当 GCP 用）。

正文是英文，因为他们一直用英文回。四个问题里有三个会直接影响提交是否合规，所以都写了"为什么问"。

---

**To:** (the account-provisioning thread)
**Cc:** a3-workshop-hackathon@lists.berkeley.edu
**Subject:** Re: CHIA hackathon account access — #27 final-submission questions

Hi,

Thank you again for the compute support and for the several rounds of account fixes — the
funded project worked cleanly and we are wrapping up. Both `c2d-standard-8` instances in
`us-east1-b` were created on Sep 22 and Sep 23 and we will delete them as soon as the final
submission is uploaded, so the sponsored usage ends there.

We are submitting HotCRP paper **#27**, "Does Agentic Architecture Discovery Reproduce? An
Audit Gate That Blocked Its Own Headline Result". It runs entirely in the official
`ghcr.io/ucb-bar/chia-champsim` image (pinned by digest), reports a **Blocked** verdict from
our own publish gate as its headline result, and releases the loop, the raw cells, the
digests and the self-audit corrections.

Four things we could not resolve from the announcement or the submission form, and would
rather ask than guess:

1. **Does the A3 workshop's 2-4 page limit apply to hackathon submissions?** The workshop
   call states "Paper length: 2-4 pages with IEEE or ACM format, excluding references", and
   the hackathon announcement states a one-page maximum for the Aug 25 proposals, but we
   could not find a length rule for the final hackathon submission in either place. Our
   paper is currently 9 pages in two-column ACM format (plus 6 references). If the 2-4 page
   workshop rule applies to the hackathon track, we will compress it -- we would rather cut
   the right sections on your guidance than guess and risk a desk reject.

2. **How should the required open-source-artifact URL interact with anonymity?** The
   HotCRP form marks an artifact URL as required, and our repository is public under a
   personal account, so anyone with the form can follow the URL to an identity while the
   paper itself is submitted anonymously. We have deliberately kept the repository URL out of
   the paper text, but the form field still exposes it. Is a personal-account public repo
   acceptable here, or would you prefer we point the field at an anonymized mirror (e.g. an
   anonymous view-only link) for the review period?

3. **Is it acceptable that the artifact URL targets a branch rather than `main`?** Our `main`
   is frozen at the earlier protocol-validation state on purpose, and the complete evidence
   lives on a working branch. We assumed a branch link is fine because it is a stable URL, but
   if reviewers are expected to land on the repository root, we will merge forward before the
   deadline instead.

4. **AI assistance disclosure.** The form has an AI Review Consent / Acknowledgement field,
   which we have completed, and we added an "AI assistance in this work" statement to the
   paper. Since the paper's subject is auditing generated evaluation artifacts — the
   annotators are language models and the loop, scripts and draft were produced by an AI
   agent under the author's direction — is the in-paper statement the form you would prefer,
   or should the detail live in a separate artifact note?

Nothing here is a blocker on our side; we will submit on time regardless, and where we have
had to choose we have written the choice down in the paper rather than leaving it implicit.

Thank you for the support and for the quick replies on the account issues.

Best regards,
Listen Jiang
(submitter, HotCRP #27)

---

## 发之前请注意（这些是我这边的判断依据，别写进邮件）

- **问题 1 的证据链（2026-09-24 现场重查，不再凭记忆）**：
  (a) 公告 `chialoops.ai/blog/chia-hackathon-a3-micro-2026/` 只有提案阶段的
  "Proposals are short — 1 page max — and are due Aug 25, 2026"，**通篇没有终稿长度要求**；
  (b) 但 A³ workshop 的征稿页 `ieeetcca.org/…/submit-agentic-hardware-research…` 明写
  **"Paper length: 2-4 pages with IEEE or ACM format, excluding references"** —— 那是
  **workshop 论文轨**的规则，该页对 hackathon 只字未提。
  所以问题不是"有没有页数限制"，而是**"workshop 的 2-4 页是否管到 hackathon 提交"**。
  我早先在 README 里写的"官方要求 4 页"（ops log §19 的第七缺陷）是无出处的杜撰；
  现在有了一个**有出处但适用范围未确认**的数，性质不同，必须在邮件里问清。
  **8 页 vs 2-4 页是 2-4 倍的差距**，若适用就是 desk-reject 级别，所以同时准备一份压缩版更稳。
- **问题 2 是真的会破匿名**：`README.md` 里的公开 artifact 地址是 `github.com/ListenJ/…`。
  HotCRP 的必填字段会把这条 URL 呈现给评审 —— 论文里我已经删掉 URL 保持盲审，但表单字段删不掉
  （删了会显示 "not ready for review"）。这是组织者能一句话裁定的事，不该由我猜。
- **问题 3 与既有决定有关**：你之前选择"HotCRP 链接改指分支"，`main` 冻结在 9/21 的 stub 态是
  有意为之；问一句的成本很低，收益是评审不会点开一个看起来像空壳的根目录。
- **问题 4**：AI 声明已补（ops log §29），措辞按本文对生成物的同一标准写；他们若要别的格式，
  改一段就够。
- 邮件里"用完后立刻拆机"这句一旦发出就是承诺：步骤 4 的 `gcloud compute instances delete`
  要真的做（两台目前仍 RUNNING 且在计费）。
