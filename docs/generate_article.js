/* 氧气瓶倒伏智能检测技术方案 — 领导阅读版（文章式，理论为重点） */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, PageNumber, AlignmentType, HeadingLevel,
  WidthType, BorderStyle, ShadingType,
} = require("docx");
const fs = require("fs");
const { imageSize } = require("image-size");

/* ── 配色（DM-1 科技派生，正文纯黑）── */
const P = {
  primary: "0B1220", body: "000000", secondary: "606060",
  headerBg: "1B6B7A", headerText: "FFFFFF", innerLine: "C8DDE2", surface: "EDF3F5",
};

/* ── 组件 ── */
const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 320, after: 140, line: 312 },
  children: [new TextRun({ text, bold: true, size: 30, color: P.primary,
    font: { ascii: "Times New Roman", eastAsia: "SimHei" } })],
});
const h2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 240, after: 100, line: 312 },
  children: [new TextRun({ text, bold: true, size: 26, color: P.primary,
    font: { ascii: "Times New Roman", eastAsia: "SimHei" } })],
});
const body = (text, opts = {}) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  indent: { firstLine: 480 },
  spacing: { line: 312, after: opts.after ?? 80 },
  children: [new TextRun({ text, size: 24, color: P.body,
    font: { ascii: "Times New Roman", eastAsia: "SimSun" } })],
});
const bodyRuns = (runs) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  indent: { firstLine: 480 },
  spacing: { line: 312, after: 80 },
  children: runs.map(r => new TextRun({ size: 24, color: P.body,
    font: { ascii: "Times New Roman", eastAsia: "SimSun" }, ...r })),
});
const caption = (text) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 80, after: 200, line: 312 },
  children: [new TextRun({ text, size: 21, color: P.secondary,
    font: { ascii: "Times New Roman", eastAsia: "SimSun" } })],
});
const figure = (path, widthPx) => {
  const dim = imageSize(fs.readFileSync(path));
  const h = Math.round(widthPx * dim.height / dim.width);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 40 },
    children: [new ImageRun({ data: fs.readFileSync(path),
      transformation: { width: widthPx, height: h }, type: "jpg" })],
  });
};

/* ── 验证结果表 ── */
const cell = (text, { header = false, w = 25 } = {}) => new TableCell({
  width: { size: w, type: WidthType.PERCENTAGE },
  shading: header ? { type: ShadingType.CLEAR, fill: P.headerBg } : undefined,
  margins: { top: 60, bottom: 60, left: 120, right: 120 },
  children: [new Paragraph({
    alignment: header ? AlignmentType.CENTER : AlignmentType.LEFT,
    spacing: { line: 312 },
    children: [new TextRun({ text, size: 21, bold: header,
      color: header ? P.headerText : P.body,
      font: { ascii: "Times New Roman", eastAsia: header ? "SimHei" : "SimSun" } })],
  })],
});
const row = (cells, i) => new TableRow({
  cantSplit: true,
  children: cells.map((t, j) => cell(t, { header: i === 0, w: j === 0 ? 34 : 22 })),
});
const resultTable = new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: P.headerBg },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: P.headerBg },
    left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: P.innerLine },
    insideVertical: { style: BorderStyle.NONE },
  },
  rows: [
    row(["对象", "三维夹角", "伸长比", "判定"], 0),
    row(["站立瓶（推车上）", "3°", "37.5", "直立"], 1),
    row(["被推车半遮挡的瓶", "36°", "6.1", "直立（可信度中等）"], 2),
    row(["躺倒瓶", "88°", "37.5", "倒伏"], 3),
    row(["躺倒瓶", "69°", "7.5", "倒伏"], 4),
  ],
});

/* ── 正文 ── */
const children = [
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 120, line: Math.ceil(18 * 23), lineRule: "atLeast" },
    children: [new TextRun({ text: "氧气瓶倒伏智能检测技术方案", bold: true, size: 36,
      color: P.primary, font: { ascii: "Times New Roman", eastAsia: "SimHei" } })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 240, line: 312 },
    children: [new TextRun({ text: "算法验证已通过 · 2026年10月", size: 21, color: P.secondary,
      font: { ascii: "Times New Roman", eastAsia: "SimSun" } })],
  }),

  h1("一、要解决的问题"),
  body("氧气瓶在存放和使用过程中可能因碰撞、支架失效等原因倾倒，倾倒的气瓶存在阀门断裂、瓶体滚动的安全风险。本方案在固定摄像头覆盖的存放区域，对视频画面自动识别氧气瓶并判断其是否处于倒伏状态，发现倒伏立即告警。现场约束是：单目普通摄像头、大俯拍角度安装（实测相机俯仰约 32°~56°）、全部算法本地离线运行。"),

  h1("二、难点：平面图像回答不了三维姿态"),
  body("判断倒伏，本质是判断瓶子轴向与重力方向的夹角：直立约 0°，躺倒约 90°。这是一个三维量。而摄像头拍到的是三维世界在平面上的投影，深度维度在成像时被丢掉了。一根指向镜头的杆子和一根竖直的杆子，在照片里可能形状完全一样——单看二维图像，这个维度上的信息已经不存在了。"),
  h2("盲区一：俯拍把直立瓶\u201c压胖\u201d"),
  body("从高处往下拍时，站立的圆柱在画面里被压缩变矮，轮廓高宽比随俯角增大不断向 1 靠近。现场俯角达五六十度，若按检测框的高宽比判倒伏，会把站立的瓶误判成倒伏。"),
  h2("盲区二：顺着镜头方向躺倒的瓶，看起来像站着"),
  body("这是透视投影的固有性质。所有竖直线在图像里汇聚于竖直灭点；而顺着视线方向躺平的瓶子，其轴向灭点同样落在画面上方，两者非常接近。按现场相机参数（俯仰 -55.9°、垂直视场角 47.1°）精确计算，这样的躺倒瓶在图像里的轴向与它所在位置的重力方向夹角只有约 4°——在画面上它瓶头朝上、身形竖直，与站立几乎无法区分。"),
  bodyRuns([
    { text: "结论：" , bold: true },
    { text: "任何只在二维图像里找角度、找比例的方法，对这类姿态必然漏判。这不是算法好坏的问题，而是成像过程把判断所需的深度信息丢掉了。" },
  ]),

  h1("三、方案原理：把丢掉的深度维度找回来"),
  h2("单目几何模型恢复三维点云"),
  body("近年出现的单目几何大模型（本方案采用微软开源的 MoGe）可以从单张照片推算每个像素的三维坐标，输出一张点云，相当于把投影时丢掉的深度维度恢复回来。它不需要双目相机、不需要深度相机，也不需要事先标定。"),
  h2("瓶子轴向：对瓶身点云做主成分分析"),
  body("瓶身是细长圆柱。把分割出的瓶身像素的三维点做主成分分析（PCA），最大主方向就是瓶子真实的三维轴向。即使瓶子在图像里被压得很短，它的三维点沿轴向的深度差依然拉开了——这正是纯二维方法做不到的。"),
  h2("重力方向：地面就是基准"),
  body("重力方向不需要任何额外的模型去估计。对画面下部的地面点云做平面拟合（RANSAC 随机采样一致），拟合出的平面法向量就是重力方向——地面在哪，\u201c上\u201d就在哪。这一步同时消除了传统方案里相机姿态估计网络的误差来源。"),
  h2("判定与体系自洽性"),
  body("瓶子轴向与重力向量的夹角，就是瓶子真实的倾角。实测站立瓶 3°、躺倒瓶 88°，判决阈值取 45°，界限清晰。这套体系有两个可靠性质：其一，轴向与重力来自同一份点云，天然自洽，不存在两个模型各自的小误差叠加后不可控的问题；其二，全程只需要方向、不需要绝对尺度，因此既不需要标定相机高度，也不需要标定焦距。"),

  h1("四、系统组成"),
  body("四个模型各司其职：YOLO 检测器负责找到画面里的氧气瓶（使用自有场景数据训练的模型）；SAM3 分割模型负责把每个瓶子从背景中精确抠出，保证参与计算的点云只含瓶身；MoGe 负责恢复三维点云；判定模块计算轴向与地面法向的夹角并给出结论。固定机位下重力方向不变，启动时校准一次、运行期复用，常规视频帧的主要开销只有目标检测，满足实时性要求。"),

  h1("五、验证结果"),
  body("用现场三张实景照片做了端到端验证（车间环境、大俯拍）。地面拟合内点率 72%，判定全部符合事实。其中躺倒瓶的 88° 尤其有说服力：该瓶在图像里被强烈压缩，若按二维高宽比只有 0.31，而三维角度清晰无误地指出它近乎水平。", { after: 120 }),
  new Paragraph({
    keepNext: true,
    spacing: { before: 120, after: 60 },
    children: [new TextRun({ text: "验证结果汇总", bold: true, size: 21,
      color: P.body, font: { ascii: "Times New Roman", eastAsia: "SimHei" } })],
  }),
  resultTable,
  caption("表 1  现场实景照片的端到端验证结果"),
  figure("../data/test3d_2.jpg", 330),
  caption("图 1  躺倒瓶被正确判定（三维夹角 88°，标注 TIPPED；黄蓝箭头为画面各处重力方向，绿箭头为该瓶处重力方向）"),
  body("已知边界：重度遮挡会减少可见点数、影响轴向估计（系统以\u201c伸长比\u201d指标提示可信度，过低时转人工复核）；检测模型对画面中的工业管件存在个别误检，需补充负样本重训；\u201c瓶头朝镜头方向躺倒\u201d的实物照片尚未采集，该场景是本方案相对二维方法提升最大的用例，部署验收前需补拍确认。"),

  h1("六、部署建议与后续工作"),
  body("相机安装直接决定算法上限，建议遵循四点：俯角不超过 45°；视线方向尽量垂直于瓶排走向；画面下部保留足够地面（地面拟合依赖）；优先选用定焦枪机。"),
  body("后续工作按优先级：一是夜间与逆光等真实光照条件下的复测；二是补充工业管件负样本重训检测模型，消除误检；三是与现有监控平台对接告警推送与截图存证；四是训练分割版检测模型，进一步提升遮挡场景下的轴向估计精度。"),
];

/* ── 组装 ── */
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimSun" }, size: 24, color: P.body },
        paragraph: { spacing: { line: 312 } },
      },
      heading1: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimHei" }, size: 30, bold: true, color: P.primary },
        paragraph: { spacing: { before: 320, after: 140, line: 312 }, outlineLevel: 0 },
      },
      heading2: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimHei" }, size: 26, bold: true, color: P.primary },
        paragraph: { spacing: { before: 240, after: 100, line: 312 }, outlineLevel: 1 },
      },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, bottom: 1440, left: 1701, right: 1417 },
      },
    },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "888888" })],
    })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("氧气瓶倒伏智能检测技术方案.docx", buf);
  console.log("生成完成: 氧气瓶倒伏智能检测技术方案.docx");
});
