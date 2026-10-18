"""OpenPose COCO_18 JSON boundary; no custom head/jaw/pubic bones."""

from pydantic import BaseModel, Field, FiniteFloat, model_validator

from study_scene import Point

KEYPOINT_NAMES = (
    "Nose",
    "Neck",
    "RShoulder",
    "RElbow",
    "RWrist",
    "LShoulder",
    "LElbow",
    "LWrist",
    "RHip",
    "RKnee",
    "RAnkle",
    "LHip",
    "LKnee",
    "LAnkle",
    "REye",
    "LEye",
    "REar",
    "LEar",
)
CONNECTIONS = (
    ("Neck", "RShoulder"),
    ("Neck", "LShoulder"),
    ("RShoulder", "RElbow"),
    ("RElbow", "RWrist"),
    ("LShoulder", "LElbow"),
    ("LElbow", "LWrist"),
    ("Neck", "RHip"),
    ("RHip", "RKnee"),
    ("RKnee", "RAnkle"),
    ("Neck", "LHip"),
    ("LHip", "LKnee"),
    ("LKnee", "LAnkle"),
    ("Neck", "Nose"),
    ("Nose", "REye"),
    ("REye", "REar"),
    ("Nose", "LEye"),
    ("LEye", "LEar"),
    ("RShoulder", "REar"),
    ("LShoulder", "LEar"),
)


class Person(BaseModel):
    person_id: list[int] = Field(default_factory=lambda: [-1])
    pose_keypoints_2d: list[FiniteFloat] = Field(min_length=54, max_length=54)
    face_keypoints_2d: list[FiniteFloat] = Field(default_factory=list)
    hand_left_keypoints_2d: list[FiniteFloat] = Field(default_factory=list)
    hand_right_keypoints_2d: list[FiniteFloat] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_confidences(self):
        if any(not 0 <= c <= 1 for c in self.pose_keypoints_2d[2::3]):
            raise ValueError("OpenPose confidences must be between 0 and 1.")
        return self

    def points(self) -> dict[str, Point]:
        return {
            name: (self.pose_keypoints_2d[3 * i], self.pose_keypoints_2d[3 * i + 1])
            for i, name in enumerate(KEYPOINT_NAMES)
            if self.pose_keypoints_2d[3 * i + 2] > 0
        }


class OpenPoseFrame(BaseModel):
    version: float = 1.3
    people: list[Person] = Field(min_length=1)

    def points(self) -> dict[str, Point]:
        if len(self.people) != 1:
            raise ValueError(
                "The current skin study requires exactly one OpenPose person."
            )
        points = self.people[0].points()
        missing = set(KEYPOINT_NAMES[:14]) - points.keys()
        if missing:
            raise ValueError(
                f"Missing body/head attachment landmarks: {sorted(missing)}"
            )
        return points
